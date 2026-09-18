#!/usr/bin/env python3
"""
Generate a markdown summary for GitHub Actions output
"""

import json
import os
from datetime import datetime

def generate_summary():
    """Generate markdown summary from the risk report"""

    report_file = 'pr-risk-report.json'

    # Check if report exists
    if not os.path.exists(report_file):
        print("⚠️ Risk report not found")
        return

    # Load report
    with open(report_file, 'r') as f:
        report = json.load(f)

    summary = report['summary']

    # Determine status emoji
    if summary['critical_risks'] > 0:
        status = "🔴"
        status_text = "CRITICAL RISKS DETECTED"
    elif summary['high_risks'] >= 3:
        status = "🟠"
        status_text = "HIGH RISKS DETECTED"
    else:
        status = "🟢"
        status_text = "RISKS WITHIN LIMITS"

    # Build markdown
    markdown = f"""
## {status} PR Risk Analysis Report

**Status**: {status_text}

### Summary Metrics

| Metric | Count | Threshold |
|--------|-------|-----------|
| Total PRs Analyzed | {summary['total_prs']} | - |
| Critical Risk PRs | {summary['critical_risks']} | ≥ 1 ❌ |
| High Risk PRs | {summary['high_risks']} | ≥ 3 ⚠️ |
| Risk Percentage | {summary['risk_percentage']}% | > 25% ❌ |

### Analysis Details

- **Repository**: {report['repository']}
- **Date Range**: Last {report['date_range']['days']} days
- **Analysis Time**: {report['timestamp']}

"""

    # Critical risk PRs section
    if report['critical_risk_prs']:
        markdown += "### 🔴 Critical Risk Pull Requests\n\n"
        for pr in report['critical_risk_prs']:
            markdown += f"#### #{pr['number']}: {pr['title']}\n"
            markdown += f"- **Author**: {pr['author']}\n"
            markdown += f"- **Risk Score**: {pr['overall_score']}/10\n"
            markdown += f"- **URL**: [{pr['url'].split('/')[-1]}]({pr['url']})\n"

            if pr['security_risks']:
                markdown += "- **Security Issues**:\n"
                for risk in pr['security_risks']:
                    markdown += f"  - [{risk['severity'].upper()}] {risk['message']}\n"

            if pr['test_risks']:
                markdown += "- **Test Issues**:\n"
                for risk in pr['test_risks']:
                    markdown += f"  - [{risk['severity'].upper()}] {risk['message']}\n"

            if pr['quality_risks']:
                markdown += "- **Quality Issues**:\n"
                for risk in pr['quality_risks']:
                    markdown += f"  - [{risk['severity'].upper()}] {risk['message']}\n"

            markdown += "\n"

    # High risk PRs section
    if report['high_risk_prs']:
        markdown += "### 🟠 High Risk Pull Requests\n\n"
        for pr in report['high_risk_prs'][:10]:  # Show top 10
            markdown += f"- **#{pr['number']}** ({pr['author']}): {pr['title'][:60]}"
            markdown += f" - Score: {pr['overall_score']}/10\n"

        if len(report['high_risk_prs']) > 10:
            markdown += f"- ... and {len(report['high_risk_prs']) - 10} more high-risk PRs\n"

        markdown += "\n"

    # Risk distribution
    if report.get('risk_distribution'):
        markdown += "### 📊 Risk Distribution\n\n"
        markdown += "| Risk Type | Count |\n"
        markdown += "|-----------|-------|\n"

        for risk_type, count in sorted(
            report['risk_distribution'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            markdown += f"| {risk_type} | {count} |\n"

        markdown += "\n"

    # Recommendations
    if summary['critical_risks'] > 0 or summary['risk_percentage'] > 25:
        markdown += "### 📋 Recommendations\n\n"
        markdown += "1. **Review Critical PRs**: Immediately review and address critical risk PRs\n"
        markdown += "2. **Strengthen Reviews**: Enforce minimum reviewer counts (2+) for all PRs\n"
        markdown += "3. **Test Coverage**: Increase test coverage requirements\n"
        markdown += "4. **Security Scanning**: Enable/enhance SAST and dependency scanning\n"
        markdown += "5. **Training**: Consider security awareness training for the team\n\n"
    else:
        markdown += "### ✅ Status\n\n"
        markdown += "Risk levels are within acceptable thresholds. Continue monitoring.\n\n"

    # Print to stdout
    print(markdown)

if __name__ == '__main__':
    generate_summary()
