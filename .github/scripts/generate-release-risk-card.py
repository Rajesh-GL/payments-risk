#!/usr/bin/env python3
"""
Release Risk Card Generator

Aggregates ALL PRs merged in a date range into ONE AI-analyzed
"Release Risk Assessment":
  1. A styled HTML card, screenshotted to PNG via headless Chromium
     (Playwright) and embedded into the GitHub Actions Job Summary.
  2. A plain-Markdown text summary (searchable/accessible, unlike the
     image) appended right after it, ending in a clear PASS/FAIL verdict.
  3. A JSON report and the raw HTML/PNG saved to disk for the artifact
     upload step.

Why a screenshot for the card: GitHub sanitizes Job Summary markdown and
strips custom CSS / styled <div> layouts, so a polished, pixel-controlled
card can only be delivered as an embedded image. The Markdown summary
exists precisely to cover what the image can't: text search, screen
readers, and diffability across runs.
"""

import os
import sys
import json
import base64
import argparse
import re
from datetime import datetime, timedelta
from typing import List, Dict

import requests
import anthropic

SEVERITY_COLORS = {
    "Critical": {"main": "#7c3aed", "bg": "#f5f3ff", "text": "#6d28d9"},
    "High":     {"main": "#ef4444", "bg": "#fef2f2", "text": "#b91c1c"},
    "Medium":   {"main": "#f59e0b", "bg": "#fffbeb", "text": "#b45309"},
    "Low":      {"main": "#22c55e", "bg": "#f0fdf4", "text": "#15803d"},
}

ALERT_STYLES = {
    "caution": {"bg": "#fee2e2", "border": "#fca5a5", "text": "#991b1b", "icon": "🔺"},
    "warning": {"bg": "#fef3c7", "border": "#fcd34d", "text": "#92400e", "icon": "⚠️"},
}

SEVERITY_EMOJI = {
    "Critical": "🔴",
    "High": "🟠",
    "Medium": "🟡",
    "Low": "🟢",
}

# The risk level at/above which the pipeline should fail
FAIL_ON_LEVEL = "Critical"


class ReleaseRiskAnalyzer:
    def __init__(self, repo: str, github_token: str, claude_api_key: str, days: int = 7, max_prs: int = 15):
        self.repo = repo
        self.github_headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"
        self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
        self.days = days
        self.max_prs = max_prs
        self.date_from = datetime.now() - timedelta(days=days)

    def fetch_prs(self) -> List[Dict]:
        date_from_str = self.date_from.isoformat().split('T')[0]
        query = f'repo:{self.repo} is:pr is:merged merged:>={date_from_str}'
        url = f"{self.base_url}/search/issues"
        params = {'q': query, 'sort': 'updated', 'order': 'desc', 'per_page': 100}
        try:
            resp = requests.get(url, headers=self.github_headers, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get('items', [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching PRs: {e}")
            return []

    def get_pr_diff(self, pr_number: int, max_len: int = 2500) -> str:
        try:
            url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}"
            r = requests.get(url, headers=self.github_headers, timeout=10)
            r.raise_for_status()
            diff_url = r.json()['diff_url']
            d = requests.get(diff_url, headers=self.github_headers, timeout=10)
            d.raise_for_status()
            text = d.text
            return text[:max_len] + ("\n... (truncated)" if len(text) > max_len else "")
        except Exception as e:
            return f"(could not fetch diff: {e})"

    def get_pr_files(self, pr_number: int) -> List[Dict]:
        try:
            url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/files"
            r = requests.get(url, headers=self.github_headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return []

    def build_context(self, prs: List[Dict]) -> str:
        chunks = []
        for pr in prs[:self.max_prs]:
            number = pr['number']
            files = self.get_pr_files(number)
            file_list = ", ".join(f['filename'] for f in files[:15])
            diff = self.get_pr_diff(number)
            chunks.append(
                f"### PR #{number}: {pr['title']}\n"
                f"Author: {pr['user']['login']}\n"
                f"Files changed ({len(files)}): {file_list}\n"
                f"Diff:\n```\n{diff}\n```\n"
            )
        return "\n\n".join(chunks)

    def analyze(self, prs: List[Dict]) -> Dict:
        context = self.build_context(prs)

        prompt = f"""
You are a senior release engineer and security reviewer. Assess the combined
risk of shipping a release that bundles the following {len(prs)} merged pull
requests as ONE cohesive change set.

{context}

Respond with ONLY a single JSON object (no prose, no markdown fences) in
exactly this shape:

{{
  "overall_score": <integer 0-10>,
  "risk_level": "Critical" | "High" | "Medium" | "Low",
  "summary": "<2-4 sentence plain-English summary referencing the specific changes>",
  "risk_dimensions": [
    {{
      "name": "<short dimension name relevant to the ACTUAL diffs, e.g. 'Schema Changes', 'Calculation Engine Changes', 'Auth & Permissions Changes', 'Data Migration' - only include dimensions with real supporting evidence>",
      "severity_label": "Critical" | "High" | "Medium" | "Low",
      "score": <integer 0-10>,
      "description": "<2-4 sentences of specific technical detail, referencing real file/function/table names from the diff>",
      "alert": {{"type": "caution", "text": "<short line>"}} or {{"type": "warning", "text": "<short line>"}} or null,
      "tag": "<optional short label like 'Impact: Core calculation'>" or null
    }}
  ],
  "services_affected": [
    {{"name": "<service/component name>", "detail": "<short clause>"}}
  ],
  "key_risks": [
    "<one specific, concrete risk statement>"
  ],
  "recommended_window": "<e.g. 'Scheduled maintenance', 'Any business hours', 'Off-peak only'>",
  "rollback_plan_required": true | false
}}

Do not invent categories with no supporting evidence in the diffs. Only set
rollback_plan_required to true if a dimension involves schema/data changes
that would be hard to reverse.
"""

        message = self.claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            raise ValueError(f"Claude did not return parseable JSON:\n{response_text[:500]}")
        return json.loads(json_match.group())


def render_html(data: Dict, repo: str, days: int) -> str:
    level = data.get('risk_level', 'Medium')
    colors = SEVERITY_COLORS.get(level, SEVERITY_COLORS['Medium'])
    score = data.get('overall_score', 0)

    def dim_html(dim: Dict) -> str:
        dcolors = SEVERITY_COLORS.get(dim.get('severity_label', 'Medium'), SEVERITY_COLORS['Medium'])
        alert = dim.get('alert')
        alert_html = ""
        if alert:
            astyle = ALERT_STYLES.get(alert.get('type', 'warning'), ALERT_STYLES['warning'])
            alert_html = f"""
            <div style="margin-top:12px;padding:10px 14px;border-radius:8px;
                        background:{astyle['bg']};border:1px solid {astyle['border']};
                        color:{astyle['text']};font-size:13px;font-weight:600;">
              {astyle['icon']} {alert['text']}
            </div>"""
        tag_html = ""
        if dim.get('tag'):
            tag_html = f"""<span style="display:inline-block;margin-top:10px;padding:3px 10px;
                          border-radius:12px;background:#eef2ff;color:#4338ca;
                          font-size:12px;font-weight:600;">{dim['tag']}</span>"""
        return f"""
        <div style="border:1px solid #e5e7eb;border-radius:12px;padding:16px 18px;margin-bottom:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div style="font-weight:700;font-size:15px;color:#111827;">{dim.get('name','')}</div>
            <div style="display:flex;align-items:center;gap:6px;font-size:13px;font-weight:600;color:{dcolors['text']};white-space:nowrap;">
              <span style="width:9px;height:9px;border-radius:50%;background:{dcolors['main']};display:inline-block;"></span>
              {dim.get('severity_label','')} ({dim.get('score','?')}/10)
            </div>
          </div>
          <div style="font-size:13.5px;line-height:1.55;color:#374151;">{dim.get('description','')}</div>
          {tag_html}
          {alert_html}
        </div>"""

    dims_html = "".join(dim_html(d) for d in data.get('risk_dimensions', []))

    services_html = "".join(
        f"""<span style="display:inline-block;margin:4px 6px 0 0;padding:5px 12px;
             border-radius:14px;background:#eef2ff;color:#3730a3;font-size:12.5px;font-weight:600;">
             {s.get('name','')} <span style="font-weight:400;color:#4f46e5;">({s.get('detail','')})</span></span>"""
        for s in data.get('services_affected', [])
    )
    services_section = ""
    if services_html:
        services_section = (
            "<div style='font-weight:800;font-size:15px;color:#111827;margin:20px 0 10px;'>Services Affected</div>"
            f"<div>{services_html}</div>"
        )

    risks_html = "".join(
        f"""<div style="display:flex;gap:8px;margin-bottom:10px;font-size:13.5px;color:#374151;line-height:1.5;">
              <span style="color:#f59e0b;">⚠️</span><span>{r}</span>
            </div>"""
        for r in data.get('key_risks', [])
    )

    rollback = "✅ YES" if data.get('rollback_plan_required') else "➖ Not required"

    circumference = 2 * 3.14159 * 54
    progress = max(0, min(score, 10)) / 10 * circumference

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:32px; background:#f3f4f6;
          font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; }}
</style></head>
<body>
  <div id="card" style="width:460px;margin:0 auto;background:#ffffff;border-radius:16px;
              border:1px solid #e5e7eb;border-left:5px solid {colors['main']};
              box-shadow:0 4px 20px rgba(0,0,0,0.06);padding:28px 30px;">

    <div style="text-align:center;font-size:19px;font-weight:800;color:#111827;margin-bottom:22px;">
      Release Risk Assessment
    </div>

    <div style="display:flex;justify-content:center;margin-bottom:10px;">
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r="54" fill="none" stroke="#e5e7eb" stroke-width="10"/>
        <circle cx="70" cy="70" r="54" fill="none" stroke="{colors['main']}" stroke-width="10"
                stroke-linecap="round" stroke-dasharray="{circumference:.1f}"
                stroke-dashoffset="{circumference - progress:.1f}"
                transform="rotate(-90 70 70)"/>
        <text x="70" y="66" text-anchor="middle" font-size="34" font-weight="800" fill="#111827">{score}</text>
        <text x="70" y="86" text-anchor="middle" font-size="12" fill="#9ca3af">/ 10</text>
      </svg>
    </div>
    <div style="text-align:center;font-weight:800;font-size:15px;color:{colors['text']};margin-bottom:18px;letter-spacing:0.3px;">
      {level.upper()}
    </div>

    <div style="font-size:13.5px;line-height:1.6;color:#4b5563;text-align:center;margin-bottom:26px;">
      {data.get('summary','')}
    </div>

    <div style="font-weight:800;font-size:15px;color:#111827;margin-bottom:14px;">Risk Dimensions</div>
    {dims_html}

    {services_section}

    <div style="font-weight:800;font-size:15px;color:#111827;margin:22px 0 12px;">⚡ Key Risks Identified</div>
    {risks_html}

    <div style="margin-top:20px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:13.5px;color:#374151;">
      <div style="margin-bottom:6px;"><b>Recommended Window:</b> {data.get('recommended_window','N/A')}</div>
      <div><b>Rollback Plan Required:</b> {rollback}</div>
    </div>

    <div style="margin-top:20px;padding-top:12px;border-top:1px dashed #e5e7eb;font-size:11px;color:#9ca3af;text-align:center;">
      {repo} &middot; merged PRs from last {days} day(s) &middot; generated by Claude AI
    </div>
  </div>
</body></html>
"""


def render_png(html: str, output_path: str):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 620, "height": 900})
        page.set_content(html, wait_until="load")
        card = page.query_selector("#card")
        if card:
            card.screenshot(path=output_path)
        else:
            page.screenshot(path=output_path, full_page=True)
        browser.close()


def render_markdown_summary(data: Dict, repo: str, days: int, prs: List[Dict]) -> str:
    """
    Plain-text/Markdown companion to the PNG card - covers what an image
    can't: full-text search, screen readers, and a clean diff between runs.
    Uses GitHub's native alert syntax (rendered with colored borders/icons
    by the Job Summary renderer) instead of custom HTML.
    """
    level = data.get('risk_level', 'Medium')
    score = data.get('overall_score', 'N/A')
    emoji = SEVERITY_EMOJI.get(level, '⚪')

    lines = []
    lines.append(f"## {emoji} Release Risk Assessment - Summary Report\n")
    lines.append(f"**Overall Score:** {score}/10  ")
    lines.append(f"**Risk Level:** {level}  ")
    lines.append(f"**Repository:** {repo}  ")
    lines.append(f"**PRs Assessed:** {len(prs)} (merged in the last {days} day(s))  ")
    lines.append(f"**Generated:** {datetime.now().isoformat(timespec='seconds')}\n")

    lines.append(f"### Summary\n\n{data.get('summary', 'N/A')}\n")

    dims = data.get('risk_dimensions', [])
    if dims:
        lines.append("### Risk Dimensions\n")
        lines.append("| Dimension | Severity | Score | Details |")
        lines.append("|---|---|---|---|")
        for d in dims:
            dlevel = d.get('severity_label', 'Medium')
            demoji = SEVERITY_EMOJI.get(dlevel, '⚪')
            desc = (d.get('description') or '').replace('|', '\\|').replace('\n', ' ')
            lines.append(f"| {d.get('name','')} | {demoji} {dlevel} | {d.get('score','?')}/10 | {desc} |")
        lines.append("")

        # Call out any alerts using GitHub's native alert blocks
        for d in dims:
            alert = d.get('alert')
            if alert:
                gh_type = "CAUTION" if alert.get('type') == 'caution' else "WARNING"
                lines.append(f"> [!{gh_type}]")
                lines.append(f"> **{d.get('name','')}:** {alert.get('text','')}\n")

    services = data.get('services_affected', [])
    if services:
        lines.append("### Services Affected\n")
        for s in services:
            lines.append(f"- **{s.get('name','')}** ({s.get('detail','')})")
        lines.append("")

    risks = data.get('key_risks', [])
    if risks:
        lines.append("### Key Risks Identified\n")
        for r in risks:
            lines.append(f"- ⚠️ {r}")
        lines.append("")

    rollback = "✅ Yes" if data.get('rollback_plan_required') else "➖ Not required"
    lines.append("### Deployment Guidance\n")
    lines.append(f"- **Recommended Window:** {data.get('recommended_window', 'N/A')}")
    lines.append(f"- **Rollback Plan Required:** {rollback}\n")

    lines.append("### Pull Requests Included\n")
    for pr in prs[:25]:
        lines.append(f"- [#{pr['number']}]({pr.get('html_url','')}) {pr.get('title','')} (@{pr.get('user',{}).get('login','unknown')})")
    if len(prs) > 25:
        lines.append(f"- ... and {len(prs) - 25} more")
    lines.append("")

    # Final verdict - tied directly to the same gate that fails the job
    lines.append("---\n")
    if level == FAIL_ON_LEVEL:
        lines.append(f"### ❌ Final Verdict: FAIL\n")
        lines.append(f"Risk level **{level}** meets or exceeds the fail threshold (`{FAIL_ON_LEVEL}`). "
                      f"This pipeline run has been marked as failed - review the risk dimensions above before proceeding.\n")
    else:
        lines.append(f"### ✅ Final Verdict: PASS\n")
        lines.append(f"Risk level **{level}** is below the fail threshold (`{FAIL_ON_LEVEL}`). "
                      f"No pipeline gate was triggered, but review any High/Medium items above as appropriate.\n")

    return "\n".join(lines)


def write_step_summary(png_path: str, markdown_summary: str):
    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    with open(png_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')

    image_md = f"![Release Risk Assessment](data:image/png;base64,{b64})\n"

    combined = image_md + "\n" + markdown_summary

    if summary_file:
        with open(summary_file, 'a') as f:
            f.write(combined)
    else:
        print("(GITHUB_STEP_SUMMARY not set - printing summary to stdout instead)")
        print(markdown_summary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--github-token', required=True)
    parser.add_argument('--claude-token', required=True)
    parser.add_argument('--days', type=int, default=7)
    args = parser.parse_args()

    analyzer = ReleaseRiskAnalyzer(args.repo, args.github_token, args.claude_token, args.days)
    prs = analyzer.fetch_prs()

    if not prs:
        print(f"⚠️  No merged PRs found in the last {args.days} day(s) - nothing to assess.")
        summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
        no_pr_md = (
            f"\n### Release Risk Assessment\n\n"
            f"No PRs merged in the last {args.days} day(s). Nothing to assess.\n\n"
            f"### ✅ Final Verdict: PASS\n\nNo changes to evaluate.\n"
        )
        if summary_file:
            with open(summary_file, 'a') as f:
                f.write(no_pr_md)
        # Also write a minimal report file so the artifact upload step doesn't fail
        with open('release-risk-report.json', 'w') as f:
            json.dump({"overall_score": 0, "risk_level": "Low", "summary": "No PRs merged in range."}, f, indent=2)
        with open('release-risk-summary.md', 'w') as f:
            f.write(no_pr_md)
        sys.exit(0)

    print(f"📊 Assessing {len(prs)} merged PR(s) as one release...")
    data = analyzer.analyze(prs)

    with open('release-risk-report.json', 'w') as f:
        json.dump(data, f, indent=2)

    html = render_html(data, args.repo, args.days)
    with open('release-risk-card.html', 'w') as f:
        f.write(html)

    render_png(html, 'release-risk-card.png')

    markdown_summary = render_markdown_summary(data, args.repo, args.days, prs)
    with open('release-risk-summary.md', 'w') as f:
        f.write(markdown_summary)

    write_step_summary('release-risk-card.png', markdown_summary)

    print(json.dumps(
        {'overall_score': data.get('overall_score'), 'risk_level': data.get('risk_level')},
        indent=2
    ))

    # Gate the pipeline: fail when risk level meets/exceeds the threshold
    if data.get('risk_level') == FAIL_ON_LEVEL:
        print(f"❌ Release risk level is {FAIL_ON_LEVEL.upper()} - failing pipeline")
        sys.exit(1)

    print("✅ Release risk within acceptable limits")
    sys.exit(0)


if __name__ == '__main__':
    main()
