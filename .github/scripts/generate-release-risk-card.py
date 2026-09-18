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

Scope: changes under .github/ (workflows, CI scripts) are excluded from
analysis - this pipeline's own maintenance commits shouldn't be scored as
"release risk" alongside real application changes. A PR that touches ONLY
.github/ files is skipped entirely and listed separately in the report.

Robustness: Claude is asked for a specific JSON schema, but LLM output is
not guaranteed to match it exactly every time (e.g. it may return a list
of plain strings where a list of {name, detail} objects was asked for).
normalize_analysis() coerces whatever comes back into the expected shape
immediately after parsing, so a minor schema deviation degrades gracefully
instead of crashing the whole job deep inside HTML rendering.
"""

import os
import sys
import json
import base64
import argparse
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any

import requests
import anthropic

# Claude API model ID. Kept as a constant so it's easy to bump when
# Anthropic retires a snapshot - see https://platform.claude.com/docs/en/about-claude/model-deprecations
CLAUDE_MODEL = "claude-sonnet-5"

# Path prefix excluded from risk analysis - CI/CD pipeline config, not application code
EXCLUDED_PATH_PREFIXES = (".github/",)

VALID_SEVERITIES = ("Critical", "High", "Medium", "Low")

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


def is_excluded_path(filename: str) -> bool:
    return any(filename.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES)


def filter_diff_exclude_paths(diff_text: str) -> str:
    """
    Remove per-file hunks for excluded paths from a unified diff produced
    by GitHub's .diff endpoint. Each file's hunk starts with a line like:
        diff --git a/<path> b/<path>
    """
    sections = re.split(r'(?=^diff --git )', diff_text, flags=re.MULTILINE)
    kept = []
    for section in sections:
        if not section.strip():
            continue
        first_line = section.splitlines()[0]
        m = re.match(r'^diff --git a/(\S+) b/(\S+)', first_line)
        if m and (is_excluded_path(m.group(1)) or is_excluded_path(m.group(2))):
            continue
        kept.append(section)
    return "".join(kept)


def _coerce_severity(value: Any, default: str = "Medium") -> str:
    if isinstance(value, str):
        for v in VALID_SEVERITIES:
            if value.strip().lower() == v.lower():
                return v
    return default


def _coerce_score(value: Any, default: int = 5) -> Any:
    try:
        n = float(value)
        return int(round(max(0, min(n, 10))))
    except (TypeError, ValueError):
        return default


def normalize_analysis(raw: Dict) -> Dict:
    """
    Coerce Claude's parsed JSON into the exact shape every renderer expects,
    regardless of minor deviations from the requested schema (strings
    instead of objects, missing fields, wrong types, etc.). This is the
    single choke point where "whatever the model returned" becomes
    "guaranteed-safe data" - render_html / render_markdown_summary should
    never need defensive isinstance() checks because of this function.
    """
    if not isinstance(raw, dict):
        raw = {}

    data: Dict[str, Any] = {}

    data['overall_score'] = _coerce_score(raw.get('overall_score'), default=5)
    data['risk_level'] = _coerce_severity(raw.get('risk_level'), default="Medium")
    data['summary'] = str(raw.get('summary') or "No summary provided.")

    # risk_dimensions: list of dicts expected; tolerate plain strings
    dims_out = []
    for d in raw.get('risk_dimensions') or []:
        if isinstance(d, dict):
            alert = d.get('alert')
            if isinstance(alert, dict) and alert.get('text'):
                alert_out = {
                    "type": alert.get('type') if alert.get('type') in ('caution', 'warning') else 'warning',
                    "text": str(alert.get('text')),
                }
            else:
                alert_out = None
            dims_out.append({
                "name": str(d.get('name') or "Unnamed change"),
                "severity_label": _coerce_severity(d.get('severity_label')),
                "score": _coerce_score(d.get('score')),
                "description": str(d.get('description') or ""),
                "alert": alert_out,
                "tag": str(d['tag']) if d.get('tag') else None,
            })
        elif isinstance(d, str) and d.strip():
            dims_out.append({
                "name": d, "severity_label": "Medium", "score": 5,
                "description": "", "alert": None, "tag": None,
            })
    data['risk_dimensions'] = dims_out

    # services_affected: list of {name, detail} expected; tolerate plain strings
    services_out = []
    for s in raw.get('services_affected') or []:
        if isinstance(s, dict):
            name = s.get('name') or s.get('service') or ""
            if name:
                services_out.append({"name": str(name), "detail": str(s.get('detail') or "")})
        elif isinstance(s, str) and s.strip():
            services_out.append({"name": s, "detail": ""})
    data['services_affected'] = services_out

    # key_risks: list of plain strings expected; tolerate dicts
    risks_out = []
    for r in raw.get('key_risks') or []:
        if isinstance(r, str) and r.strip():
            risks_out.append(r)
        elif isinstance(r, dict):
            text = r.get('risk') or r.get('description') or r.get('text') or r.get('issue')
            risks_out.append(str(text) if text else json.dumps(r))
    data['key_risks'] = risks_out

    data['recommended_window'] = str(raw.get('recommended_window') or "Any business hours")
    data['rollback_plan_required'] = bool(raw.get('rollback_plan_required', False))

    return data


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
        self.skipped_prs: List[Dict] = []  # PRs excluded for touching ONLY .github/

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

    def get_pr_files(self, pr_number: int) -> List[Dict]:
        try:
            url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/files"
            r = requests.get(url, headers=self.github_headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return []

    def get_pr_diff_raw(self, pr_number: int) -> str:
        try:
            url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}"
            r = requests.get(url, headers=self.github_headers, timeout=10)
            r.raise_for_status()
            diff_url = r.json()['diff_url']
            d = requests.get(diff_url, headers=self.github_headers, timeout=10)
            d.raise_for_status()
            return d.text
        except Exception as e:
            return f"(could not fetch diff: {e})"

    def filter_relevant_prs(self, prs: List[Dict]) -> List[Dict]:
        """
        Split PRs into ones with at least one non-excluded file change
        (kept for analysis) and ones that ONLY touched excluded paths
        like .github/ (recorded in self.skipped_prs, shown separately).
        """
        relevant = []
        self.skipped_prs = []
        for pr in prs:
            files = self.get_pr_files(pr['number'])
            non_excluded = [f for f in files if not is_excluded_path(f.get('filename', ''))]
            if non_excluded:
                relevant.append(pr)
            else:
                self.skipped_prs.append(pr)
        return relevant

    def build_context(self, prs: List[Dict], max_len_per_pr: int = 2500) -> str:
        chunks = []
        for pr in prs[:self.max_prs]:
            number = pr['number']
            files = self.get_pr_files(number)
            relevant_files = [f for f in files if not is_excluded_path(f.get('filename', ''))]
            file_list = ", ".join(f['filename'] for f in relevant_files[:15])

            raw_diff = self.get_pr_diff_raw(number)
            diff = filter_diff_exclude_paths(raw_diff)
            if len(diff) > max_len_per_pr:
                diff = diff[:max_len_per_pr] + "\n... (truncated)"

            chunks.append(
                f"### PR #{number}: {pr['title']}\n"
                f"Author: {pr['user']['login']}\n"
                f"Files changed ({len(relevant_files)}, excluding .github/): {file_list}\n"
                f"Diff:\n```\n{diff}\n```\n"
            )
        return "\n\n".join(chunks)

    def analyze(self, prs: List[Dict]) -> Dict:
        context = self.build_context(prs)

        prompt = f"""
You are a senior release engineer and security reviewer. Assess the combined
risk of shipping a release that bundles the following {len(prs)} merged pull
requests as ONE cohesive change set.

Note: changes under .github/ (CI/CD pipeline config) have already been
excluded from the diffs below - only application/business code changes
are shown. Do not comment on pipeline or workflow files.

{context}

Respond with ONLY a single JSON object (no prose, no markdown fences) in
EXACTLY this shape - every list item MUST be an object with the fields
shown, never a plain string:

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
    "<one specific, concrete risk statement, as a plain string - NOT an object>"
  ],
  "recommended_window": "<e.g. 'Scheduled maintenance', 'Any business hours', 'Off-peak only'>",
  "rollback_plan_required": true | false
}}

Do not invent categories with no supporting evidence in the diffs. Only set
rollback_plan_required to true if a dimension involves schema/data changes
that would be hard to reverse. Every entry in "services_affected" must be an
object with "name" and "detail" keys - do not return plain strings there.
"""

        message = self.claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            raise ValueError(f"Claude did not return parseable JSON:\n{response_text[:500]}")
        raw = json.loads(json_match.group())
        return normalize_analysis(raw)


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
      {repo} &middot; merged PRs from last {days} day(s), excluding .github/ &middot; generated by Claude AI
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


def render_markdown_summary(data: Dict, repo: str, days: int, prs: List[Dict], skipped_prs: List[Dict]) -> str:
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
    lines.append(f"**PRs Assessed:** {len(prs)} (merged in the last {days} day(s), excluding .github/-only changes)  ")
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
            detail = f" ({s.get('detail')})" if s.get('detail') else ""
            lines.append(f"- **{s.get('name','')}**{detail}")
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

    if skipped_prs:
        lines.append("### Excluded from Analysis (only touched .github/)\n")
        for pr in skipped_prs[:25]:
            lines.append(f"- [#{pr['number']}]({pr.get('html_url','')}) {pr.get('title','')} (@{pr.get('user',{}).get('login','unknown')})")
        if len(skipped_prs) > 25:
            lines.append(f"- ... and {len(skipped_prs) - 25} more")
        lines.append("")

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


def write_no_analysis_summary(reason: str, skipped_prs: List[Dict]):
    """Used when there's nothing left to analyze after excluding .github/-only PRs."""
    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    lines = [
        "### Release Risk Assessment\n",
        f"{reason}\n",
    ]
    if skipped_prs:
        lines.append("Excluded (only touched .github/):\n")
        for pr in skipped_prs[:25]:
            lines.append(f"- [#{pr['number']}]({pr.get('html_url','')}) {pr.get('title','')}")
        lines.append("")
    lines.append("### ✅ Final Verdict: PASS\n\nNo application changes to evaluate.\n")
    md = "\n".join(lines)

    if summary_file:
        with open(summary_file, 'a') as f:
            f.write(md)

    with open('release-risk-report.json', 'w') as f:
        json.dump({"overall_score": 0, "risk_level": "Low", "summary": reason}, f, indent=2)
    with open('release-risk-summary.md', 'w') as f:
        f.write(md)


def write_error_summary(error: Exception):
    """
    Last-resort safety net: if analysis crashes for any reason (schema
    surprise we didn't anticipate, network blip, etc.), still leave a
    Job Summary and the artifact files behind instead of the run going
    completely silent on the Summary tab, which is what happened before
    this function existed.
    """
    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    md = (
        "### ❌ Release Risk Assessment - Error\n\n"
        f"The analysis script failed with an unexpected error:\n\n```\n{error}\n```\n\n"
        "This is a bug in the analysis pipeline itself (not a finding about your code). "
        "Check the step logs for the full traceback.\n"
    )
    if summary_file:
        with open(summary_file, 'a') as f:
            f.write(md)
    with open('release-risk-report.json', 'w') as f:
        json.dump({"overall_score": None, "risk_level": "Unknown", "error": str(error)}, f, indent=2)
    with open('release-risk-summary.md', 'w') as f:
        f.write(md)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--github-token', required=True)
    parser.add_argument('--claude-token', required=True)
    parser.add_argument('--days', type=int, default=7)
    args = parser.parse_args()

    analyzer = ReleaseRiskAnalyzer(args.repo, args.github_token, args.claude_token, args.days)

    try:
        all_prs = analyzer.fetch_prs()

        if not all_prs:
            reason = f"No PRs merged in the last {args.days} day(s). Nothing to assess."
            print(f"⚠️  {reason}")
            write_no_analysis_summary(reason, [])
            sys.exit(0)

        print(f"🔎 Found {len(all_prs)} merged PR(s) - filtering out .github/-only changes...")
        relevant_prs = analyzer.filter_relevant_prs(all_prs)

        if analyzer.skipped_prs:
            print(f"⏭️  Skipping {len(analyzer.skipped_prs)} PR(s) that only touched .github/:")
            for pr in analyzer.skipped_prs:
                print(f"    - #{pr['number']}: {pr['title']}")

        if not relevant_prs:
            reason = (
                f"{len(all_prs)} PR(s) merged in the last {args.days} day(s), but all of them only touched "
                f".github/ (pipeline config) - nothing else to assess."
            )
            print(f"⚠️  {reason}")
            write_no_analysis_summary(reason, analyzer.skipped_prs)
            sys.exit(0)

        print(f"📊 Assessing {len(relevant_prs)} merged PR(s) as one release (excluding .github/)...")
        data = analyzer.analyze(relevant_prs)

        with open('release-risk-report.json', 'w') as f:
            json.dump(data, f, indent=2)

        html = render_html(data, args.repo, args.days)
        with open('release-risk-card.html', 'w') as f:
            f.write(html)

        render_png(html, 'release-risk-card.png')

        markdown_summary = render_markdown_summary(data, args.repo, args.days, relevant_prs, analyzer.skipped_prs)
        with open('release-risk-summary.md', 'w') as f:
            f.write(markdown_summary)

        write_step_summary('release-risk-card.png', markdown_summary)

        print(json.dumps(
            {'overall_score': data.get('overall_score'), 'risk_level': data.get('risk_level')},
            indent=2
        ))

        if data.get('risk_level') == FAIL_ON_LEVEL:
            print(f"❌ Release risk level is {FAIL_ON_LEVEL.upper()} - failing pipeline")
            sys.exit(1)

        print("✅ Release risk within acceptable limits")
        sys.exit(0)

    except Exception as e:
        print(f"❌ Unexpected error during release risk analysis: {e}")
        write_error_summary(e)
        raise


if __name__ == '__main__':
    main()
