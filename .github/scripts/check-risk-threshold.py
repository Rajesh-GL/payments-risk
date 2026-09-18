#!/usr/bin/env python3
"""
Risk Threshold Checker - Determines if PR risks exceed acceptable thresholds
"""

import json
import sys
import os

def check_thresholds():
    """Check if risks are within acceptable thresholds"""

    report_file = 'pr-risk-report.json'

    # Check if report exists
    if not os.path.exists(report_file):
        print("⚠️  Risk report not found. Skipping threshold check.")
        return 0

    # Load report
    try:
        with open(report_file, 'r') as f:
            report = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse risk report: {e}")
        return 1

    # Extract metrics
    summary = report.get('summary', {})
    critical_risks = summary.get('critical_risks', 0)
    high_risks = summary.get('high_risks', 0)
    risk_percentage = summary.get('risk_percentage', 0)
    total_prs = summary.get('total_prs', 0)

    # Define thresholds
    CRITICAL_THRESHOLD = 1        # Fail if 1+ critical risks
    HIGH_THRESHOLD = 3             # Warn if 3+ high risks
    RISK_PCT_THRESHOLD = 25        # Fail if >25% of PRs are risky

    # Print report
    print("\n" + "="*70)
    print("PR RISK ANALYSIS - THRESHOLD EVALUATION")
    print("="*70)
    print(f"Repository: {report.get('repository', 'N/A')}")
    print(f"Date Range: {report.get('date_range', {}).get('days', 'N/A')} days")
    print("-"*70)
    print(f"Total PRs Analyzed: {total_prs}")
    print(f"Critical Risk PRs:  {critical_risks} (Threshold: {CRITICAL_THRESHOLD})")
    print(f"High Risk PRs:      {high_risks} (Threshold: {HIGH_THRESHOLD})")
    print(f"Risk Percentage:    {risk_percentage}% (Threshold: {RISK_PCT_THRESHOLD}%)")
    print("="*70)

    exit_code = 0

    # Check critical risks
    if critical_risks > 0:
        print(f"\n🔴 CRITICAL: {critical_risks} PR(s) with critical risk(s) detected")
        print("\n   Critical Risk PRs:")
        for pr in report.get('critical_risk_prs', []):
            print(f"     - #{pr['number']}: {pr['title']} (Score: {pr['overall_score']}/10)")
            print(f"       Author: {pr['author']}")
            print(f"       URL: {pr['url']}")

            if pr['security_risks']:
                print(f"       Security Issues:")
                for risk in pr['security_risks']:
                    print(f"         • [{risk['severity'].upper()}] {risk['message']}")

            if pr['test_risks']:
                print(f"       Test Issues:")
                for risk in pr['test_risks']:
                    print(f"         • [{risk['severity'].upper()}] {risk['message']}")

            if pr['quality_risks']:
                print(f"       Quality Issues:")
                for risk in pr['quality_risks']:
                    print(f"         • [{risk['severity'].upper()}] {risk['message']}")
            print()

        exit_code = 1

    # Warn about high risks
    if high_risks >= HIGH_THRESHOLD:
        print(f"\n🟠 WARNING: {high_risks} PR(s) with high risk(s) detected")
        print("   Consider reviewing these PRs for improvements:")
        for pr in report.get('high_risk_prs', [])[:5]:  # Show first 5
            print(f"     - #{pr['number']}: {pr['title']} (Score: {pr['overall_score']}/10)")
        if len(report.get('high_risk_prs', [])) > 5:
            print(f"     ... and {len(report.get('high_risk_prs', [])) - 5} more")

    # Check overall risk percentage
    if risk_percentage > RISK_PCT_THRESHOLD:
        print(f"\n🔴 CRITICAL: {risk_percentage}% of PRs are risky (threshold: {RISK_PCT_THRESHOLD}%)")
        print("   Repository has significant risk exposure. Consider implementing:")
        print("   - Stricter code review requirements")
        print("   - Enhanced testing/coverage requirements")
        print("   - Security scanning improvements")
        exit_code = 1

    # Positive result
    if exit_code == 0:
        print("\n✅ Risk analysis PASSED - All thresholds within acceptable limits")

    # Risk distribution
    if report.get('risk_distribution'):
        print("\n📊 Risk Distribution by Type:")
        for risk_type, count in sorted(
            report['risk_distribution'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            print(f"   {risk_type}: {count}")

    print("="*70 + "\n")

    return exit_code

if __name__ == '__main__':
    exit_code = check_thresholds()
    sys.exit(exit_code)
