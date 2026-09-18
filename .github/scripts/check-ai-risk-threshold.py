#!/usr/bin/env python3
"""
AI Risk Threshold Checker - Validates AI-detected risks against thresholds
"""

import json
import sys
import os

def check_ai_thresholds():
    """Check if AI-detected risks are within thresholds"""

    report_file = 'pr-risk-report-ai.json'

    if not os.path.exists(report_file):
        print("⚠️  AI risk report not found. Skipping threshold check.")
        return 0

    try:
        with open(report_file, 'r') as f:
            report = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse AI risk report: {e}")
        return 1

    summary = report.get('summary', {})
    critical_risks = summary.get('critical_risks', 0)
    high_risks = summary.get('high_risks', 0)
    medium_risks = summary.get('medium_risks', 0)
    total_prs = summary.get('total_prs', 0)

    # AI-based thresholds (stricter than rule-based)
    CRITICAL_THRESHOLD = 0        # No critical risks allowed
    HIGH_THRESHOLD = 2             # Warn if 2+ high risks
    MEDIUM_THRESHOLD = 5           # Warn if 5+ medium risks

    print("\n" + "="*70)
    print("AI-POWERED PR RISK ANALYSIS - THRESHOLD EVALUATION")
    print("="*70)
    print(f"Repository: {report.get('repository', 'N/A')}")
    print(f"AI Model: {report.get('ai_model', 'Claude 3.5 Sonnet')}")
    print(f"Analysis Type: {report.get('analysis_type', 'N/A')}")
    print("-"*70)
    print(f"Total PRs Analyzed:  {total_prs}")
    print(f"Critical Risk PRs:   {critical_risks} (Threshold: {CRITICAL_THRESHOLD})")
    print(f"High Risk PRs:       {high_risks} (Threshold: {HIGH_THRESHOLD})")
    print(f"Medium Risk PRs:     {medium_risks}")
    print("="*70)

    exit_code = 0

    # Check critical risks - STRICT
    if critical_risks > CRITICAL_THRESHOLD:
        print(f"\n🔴 CRITICAL: AI detected {critical_risks} critical risk(s)")
        print("\n   Critical Risk PRs:")
        for pr in report.get('critical_risk_prs', []):
            print(f"     - #{pr['number']}: {pr['title']}")
            print(f"       AI Risk Score: {pr.get('ai_risk_score', 'N/A')}/10")

            ai_analysis = pr.get('ai_analysis', {})
            print(f"       Severity: {ai_analysis.get('severity', 'N/A').upper()}")
            print(f"       Assessment: {ai_analysis.get('overall_assessment', 'N/A')[:100]}...")

            insights = ai_analysis.get('ai_insights', [])
            if insights:
                print(f"       AI Insights:")
                for insight in insights[:3]:
                    print(f"         • [{insight.get('severity', 'N/A').upper()}] {insight.get('category', 'N/A')}: {insight.get('issue', 'N/A')}")
            print()

        exit_code = 1

    # Check high risks
    if high_risks >= HIGH_THRESHOLD:
        print(f"\n🟠 WARNING: AI detected {high_risks} high risk(s)")
        print("   High Risk PRs:")
        for pr in report.get('high_risk_prs', [])[:5]:
            print(f"     - #{pr['number']}: {pr['title']}")
            print(f"       AI Risk Score: {pr.get('ai_risk_score', 'N/A')}/10")
            ai_analysis = pr.get('ai_analysis', {})
            insights = ai_analysis.get('ai_insights', [])
            if insights:
                print(f"       Key Issue: {insights[0].get('issue', 'N/A')}")

        if len(report.get('high_risk_prs', [])) > 5:
            print(f"     ... and {len(report.get('high_risk_prs', [])) - 5} more")
        print()

    # Summary
    if exit_code == 0 and high_risks < HIGH_THRESHOLD:
        print("\n✅ AI Risk Analysis PASSED - All thresholds within acceptable limits")

    # Risk insights
    if critical_risks > 0 or high_risks > 0:
        print("\n💡 AI Recommendations:")

        # Collect all insights
        all_insights = []
        for pr in report.get('critical_risk_prs', []):
            all_insights.extend(pr.get('ai_analysis', {}).get('ai_insights', []))
        for pr in report.get('high_risk_prs', []):
            all_insights.extend(pr.get('ai_analysis', {}).get('ai_insights', []))

        # Group by category
        categories = {}
        for insight in all_insights:
            cat = insight.get('category', 'other')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(insight)

        for category, insights in sorted(categories.items()):
            print(f"\n   **{category.upper()}** ({len(insights)} issue(s)):")
            for insight in insights[:2]:
                print(f"     • {insight.get('recommendation', insight.get('issue', 'N/A'))}")

    print("\n" + "="*70 + "\n")

    return exit_code

if __name__ == '__main__':
    exit_code = check_ai_thresholds()
    sys.exit(exit_code)
