#!/usr/bin/env python3
"""
Generate AI-powered markdown summary for GitHub Actions
"""

import json
import os

def generate_ai_summary():
    """Generate markdown summary with AI insights"""

    report_file = 'pr-risk-report-ai.json'

    if not os.path.exists(report_file):
        print("⚠️ AI risk report not found")
        return

    with open(report_file, 'r') as f:
        report = json.load(f)

    summary = report['summary']

    # Determine status
    if summary['critical_risks'] > 0:
        status = "🔴"
        status_text = "CRITICAL RISKS DETECTED BY AI"
    elif summary['high_risks'] >= 2:
        status = "🟠"
        status_text = "HIGH RISKS DETECTED BY AI"
    else:
        status = "🟢"
        status_text = "AI ANALYSIS COMPLETE - RISKS WITHIN LIMITS"

    markdown = f"""
## {status} AI-Powered PR Risk Analysis

**Status**: {status_text}
**Model**: Claude 3.5 Sonnet
**Analysis Type**: AI-Powered with Code Understanding

### Summary Metrics

| Metric | Count |
|--------|-------|
| Total PRs Analyzed | {summary['total_prs']} |
| Critical Risks 🔴 | {summary['critical_risks']} |
| High Risks 🟠 | {summary['high_risks']} |
| Medium Risks 🟡 | {summary['medium_risks']} |

### What AI Analyzed

✓ Code changes and diffs
✓ Security vulnerabilities in actual code
✓ Code quality and architecture
✓ Testing coverage and practices
✓ Performance implications
✓ Best practices violations

"""

    # Critical risks with AI insights
    if report['critical_risk_prs']:
        markdown += "### 🔴 Critical Risk PRs - AI Assessment\n\n"
        for pr in report['critical_risk_prs']:
            markdown += f"#### #{pr['number']}: {pr['title']}\n"
            markdown += f"- **Author**: {pr['author']}\n"
            markdown += f"- **AI Risk Score**: {pr.get('ai_risk_score', 'N/A')}/10\n"

            ai_analysis = pr.get('ai_analysis', {})
            markdown += f"- **AI Verdict**: {ai_analysis.get('severity', 'UNKNOWN').upper()}\n"
            markdown += f"- **Summary**: {ai_analysis.get('overall_assessment', 'No assessment')}\n"

            insights = ai_analysis.get('ai_insights', [])
            if insights:
                markdown += "- **AI Detected Issues**:\n"
                for insight in insights:
                    markdown += f"  - **{insight.get('category', 'other').upper()}** [{insight.get('severity', 'unknown').upper()}]: {insight.get('issue', 'N/A')}\n"
                    if insight.get('recommendation'):
                        markdown += f"    - 💡 {insight['recommendation']}\n"

            markdown += f"- **Confidence**: {int(ai_analysis.get('confidence', 0) * 100)}%\n"
            markdown += "\n"

    # High risks
    if report['high_risk_prs']:
        markdown += "### 🟠 High Risk PRs - AI Assessment\n\n"
        markdown += "| PR | Score | Category | Issue |\n"
        markdown += "|-------|-------|----------|-------|\n"

        for pr in report['high_risk_prs'][:10]:
            ai_analysis = pr.get('ai_analysis', {})
            insights = ai_analysis.get('ai_insights', [])

            if insights:
                first_insight = insights[0]
                category = first_insight.get('category', 'general')
                issue = first_insight.get('issue', 'N/A')[:50]
            else:
                category = ai_analysis.get('severity', 'N/A')
                issue = ai_analysis.get('overall_assessment', 'N/A')[:50]

            markdown += f"| #{pr['number']} | {pr.get('ai_risk_score', 'N/A')}/10 | {category} | {issue}... |\n"

        if len(report['high_risk_prs']) > 10:
            markdown += f"| ... | ... | ... | +{len(report['high_risk_prs']) - 10} more |\n"

        markdown += "\n"

    # Medium risks summary
    if report['medium_risk_prs']:
        markdown += f"### 🟡 Medium Risk PRs\n\n"
        markdown += f"AI identified {len(report['medium_risk_prs'])} PR(s) with medium-level risks. "
        markdown += "These should be reviewed for best practices improvements.\n\n"

    # AI insights by category
    all_insights = []
    for pr in report.get('critical_risk_prs', []):
        all_insights.extend(pr.get('ai_analysis', {}).get('ai_insights', []))
    for pr in report.get('high_risk_prs', []):
        all_insights.extend(pr.get('ai_analysis', {}).get('ai_insights', []))

    if all_insights:
        markdown += "### 📊 Risk Distribution by Category\n\n"

        categories = {}
        for insight in all_insights:
            cat = insight.get('category', 'other')
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1

        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            markdown += f"- **{cat.upper()}**: {count} issue(s)\n"

        markdown += "\n"

    # Recommendations
    if summary['critical_risks'] > 0 or summary['high_risks'] > 0:
        markdown += "### 💡 AI Recommendations\n\n"

        # Collect unique recommendations
        recommendations = set()
        for pr in report.get('critical_risk_prs', []):
            insights = pr.get('ai_analysis', {}).get('ai_insights', [])
            for insight in insights:
                if insight.get('recommendation'):
                    recommendations.add(insight['recommendation'])

        for pr in report.get('high_risk_prs', []):
            insights = pr.get('ai_analysis', {}).get('ai_insights', [])
            for insight in insights:
                if insight.get('recommendation'):
                    recommendations.add(insight['recommendation'])

        for i, rec in enumerate(sorted(list(recommendations))[:5], 1):
            markdown += f"{i}. {rec}\n"

        markdown += "\n"
    else:
        markdown += "### ✅ Status\n\n"
        markdown += "AI analysis found no significant risks. Code quality is within acceptable limits.\n\n"

    # Technical details
    markdown += "### 📋 Technical Details\n\n"
    markdown += f"- **Analysis Timestamp**: {report.get('timestamp', 'N/A')}\n"
    markdown += f"- **Repository**: {report.get('repository', 'N/A')}\n"
    markdown += f"- **AI Model**: {report.get('ai_model', 'N/A')}\n"
    markdown += f"- **Analysis Type**: {report.get('analysis_type', 'N/A')}\n\n"

    markdown += "> 🤖 This analysis was performed by Claude AI. AI insights may require human verification.\n"

    print(markdown)

if __name__ == '__main__':
    generate_ai_summary()
