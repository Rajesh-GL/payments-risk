#!/usr/bin/env python3
"""
PR Risk Analyzer - Analyzes merged PRs in a date range for security, quality, and test risks
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
from collections import defaultdict

class PRRiskAnalyzer:
    """Analyzes pull requests for various risk factors"""

    def __init__(self, repo: str, token: str, days: int = 7):
        self.repo = repo
        self.token = token
        self.days = days
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = "https://api.github.com"
        self.date_from = datetime.now() - timedelta(days=days)
        self.date_from_str = self.date_from.isoformat().split('T')[0]

        # Configuration
        self.min_reviewers = 2
        self.max_files_change = 50
        self.sensitive_patterns = [
            '.env', 'config', 'credentials', 'secret',
            'password', 'token', 'key', 'apikey', 'connectionstring',
            'appsettings.json', 'secrets.json'
        ]

    def fetch_prs_in_range(self) -> List[Dict]:
        """Fetch merged PRs within the date range"""
        print(f"🔍 Fetching PRs merged after {self.date_from_str}...")

        query = f'repo:{self.repo} is:pr is:merged merged:>={self.date_from_str}'
        url = f"{self.base_url}/search/issues"
        params = {
            'q': query,
            'sort': 'updated',
            'order': 'desc',
            'per_page': 100
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            items = response.json().get('items', [])
            print(f"✓ Found {len(items)} merged PRs")
            return items
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching PRs: {e}")
            return []

    def analyze_pr_security(self, pr: Dict) -> Dict:
        """Analyze security-related risks in a PR"""
        security_risks = []

        # Fetch full PR details
        try:
            pr_url = pr['url']
            pr_detail = requests.get(pr_url, headers=self.headers, timeout=10).json()

            # Check: Number of reviewers
            reviews_url = f"{pr_url}/reviews"
            reviews = requests.get(reviews_url, headers=self.headers, timeout=10).json()
            approvals = [r for r in reviews if r['state'] == 'APPROVED']

            if len(approvals) < self.min_reviewers:
                security_risks.append({
                    'type': 'insufficient_review',
                    'severity': 'high',
                    'message': f'Only {len(approvals)} approval(s) - requires {self.min_reviewers} minimum'
                })

            # Check: Merge method (should not be squash for audit trail)
            if pr_detail.get('merge_commit_sha'):
                # Merged successfully, check for comments about concerns
                comments_url = f"{pr_url}/comments"
                try:
                    comments = requests.get(comments_url, headers=self.headers, timeout=10).json()
                    negative_keywords = ['revert', 'error', 'bug', 'security', 'danger', 'risk']
                    if any(keyword in str(comments).lower() for keyword in negative_keywords):
                        security_risks.append({
                            'type': 'concerning_comments',
                            'severity': 'medium',
                            'message': 'PR has concerning comments (error, bug, security, etc.)'
                        })
                except:
                    pass

            # Check: Files changed
            files_url = f"{pr_url}/files"
            files_response = requests.get(files_url, headers=self.headers, timeout=10)
            if files_response.status_code == 200:
                files = files_response.json()

                # Large changeset
                if len(files) > self.max_files_change:
                    security_risks.append({
                        'type': 'large_changeset',
                        'severity': 'medium',
                        'message': f'{len(files)} files changed - large PRs increase review risk'
                    })

                # Sensitive file changes
                for file in files:
                    filename = file.get('filename', '').lower()
                    if any(pattern in filename for pattern in self.sensitive_patterns):
                        security_risks.append({
                            'type': 'sensitive_file_change',
                            'severity': 'critical',
                            'message': f'Sensitive file modified: {file["filename"]}'
                        })

                # Check for additions in sensitive files
                if file.get('additions', 0) > 100:
                    if any(pattern in filename for pattern in ['secret', 'password', 'token', 'key']):
                        security_risks.append({
                            'type': 'sensitive_data_addition',
                            'severity': 'critical',
                            'message': f'{file["filename"]}: Large data addition ({file["additions"]} lines)'
                        })

            # Check: Merged without approval
            if len(approvals) == 0:
                security_risks.append({
                    'type': 'no_approval',
                    'severity': 'critical',
                    'message': 'PR merged without explicit approval'
                })

        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error analyzing security for PR #{pr.get('number')}: {e}")

        return security_risks

    def analyze_pr_quality(self, pr: Dict) -> Dict:
        """Analyze code quality-related risks"""
        quality_risks = []

        try:
            pr_url = pr['url']

            # Get the commit SHA
            commit_sha = pr.get('merge_commit_sha')
            if not commit_sha:
                return quality_risks

            # Check for check runs (SonarQube, CodeQL, etc.)
            check_runs_url = f"{self.base_url}/repos/{self.repo}/commits/{commit_sha}/check-runs"
            try:
                response = requests.get(check_runs_url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    checks = response.json().get('check_runs', [])

                    for check in checks:
                        if check['status'] == 'completed':
                            # Failed checks
                            if check['conclusion'] == 'failure':
                                quality_risks.append({
                                    'type': 'check_failed',
                                    'severity': 'high',
                                    'message': f'Check failed: {check["name"]}'
                                })

                            # Parse specific quality tool failures
                            if 'sonar' in check['name'].lower():
                                if check['conclusion'] != 'success':
                                    quality_risks.append({
                                        'type': 'sonar_quality_gate_failed',
                                        'severity': 'medium',
                                        'message': f'SonarQube quality gate not met: {check["name"]}'
                                    })

                            if 'coverage' in check['name'].lower() and check['conclusion'] == 'failure':
                                quality_risks.append({
                                    'type': 'coverage_insufficient',
                                    'severity': 'medium',
                                    'message': 'Code coverage below threshold'
                                })
            except:
                pass

            # Check for status checks (older API)
            status_url = f"{self.base_url}/repos/{self.repo}/commits/{commit_sha}/status"
            try:
                response = requests.get(status_url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    status = response.json()
                    if status['state'] == 'failure':
                        quality_risks.append({
                            'type': 'commit_status_failed',
                            'severity': 'high',
                            'message': 'Commit status check failed but PR was merged'
                        })
            except:
                pass

        except Exception as e:
            print(f"⚠️  Error analyzing quality for PR #{pr.get('number')}: {e}")

        return quality_risks

    def analyze_pr_tests(self, pr: Dict) -> Dict:
        """Analyze test-related risks"""
        test_risks = []

        try:
            commit_sha = pr.get('merge_commit_sha')
            if not commit_sha:
                return test_risks

            # Get check runs for test information
            check_runs_url = f"{self.base_url}/repos/{self.repo}/commits/{commit_sha}/check-runs"
            try:
                response = requests.get(check_runs_url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    checks = response.json().get('check_runs', [])

                    for check in checks:
                        # Look for test-related checks
                        if any(keyword in check['name'].lower() for keyword in ['test', 'unit', 'integration', 'build']):
                            if check['status'] == 'completed':
                                if check['conclusion'] == 'failure':
                                    test_risks.append({
                                        'type': 'test_failure',
                                        'severity': 'critical',
                                        'message': f'Tests failed but PR merged: {check["name"]}'
                                    })
                                elif check['conclusion'] == 'neutral':
                                    test_risks.append({
                                        'type': 'test_skipped',
                                        'severity': 'medium',
                                        'message': f'Tests skipped: {check["name"]}'
                                    })
            except:
                pass

            # Check statuses API for test results
            status_url = f"{self.base_url}/repos/{self.repo}/commits/{commit_sha}/status"
            try:
                response = requests.get(status_url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    status = response.json()
                    for check in status.get('statuses', []):
                        if 'test' in check['context'].lower():
                            if check['state'] == 'failure':
                                test_risks.append({
                                    'type': 'test_failure',
                                    'severity': 'critical',
                                    'message': f'{check["context"]} failed'
                                })
            except:
                pass

        except Exception as e:
            print(f"⚠️  Error analyzing tests for PR #{pr.get('number')}: {e}")

        return test_risks

    def calculate_risk_score(self, security_risks: List, quality_risks: List, test_risks: List) -> float:
        """
        Calculate overall risk score (0-10)

        Weights:
        - Security: 40%
        - Quality: 35%
        - Tests: 25%
        """
        security_weight = 0.40
        quality_weight = 0.35
        test_weight = 0.25

        # Calculate component scores
        security_score = min(len(security_risks) * 2, 10)  # Each risk worth 2 points
        quality_score = min(len(quality_risks) * 1.5, 10)  # Each risk worth 1.5 points
        test_score = min(len(test_risks) * 3, 10)  # Each test risk worth 3 points (highest priority)

        # Weight and sum
        overall = (
            security_score * security_weight +
            quality_score * quality_weight +
            test_score * test_weight
        )

        return min(overall, 10.0)

    def analyze_pr(self, pr: Dict) -> Dict:
        """Analyze a single PR for all risk types"""
        security_risks = self.analyze_pr_security(pr)
        quality_risks = self.analyze_pr_quality(pr)
        test_risks = self.analyze_pr_tests(pr)

        risk_score = self.calculate_risk_score(security_risks, quality_risks, test_risks)

        return {
            'number': pr['number'],
            'title': pr['title'],
            'url': pr['html_url'],
            'author': pr['user']['login'],
            'merged_at': pr['merged_at'],
            'security_risks': security_risks,
            'quality_risks': quality_risks,
            'test_risks': test_risks,
            'overall_score': round(risk_score, 1)
        }

    def generate_report(self) -> Dict:
        """Generate comprehensive risk report"""
        print("\n" + "="*60)
        print("PR RISK ANALYSIS IN PROGRESS")
        print("="*60)

        prs = self.fetch_prs_in_range()

        if not prs:
            print("⚠️  No PRs found in the specified date range")
            return {
                'timestamp': datetime.now().isoformat(),
                'repository': self.repo,
                'date_range': {
                    'from': self.date_from.isoformat(),
                    'to': datetime.now().isoformat(),
                    'days': self.days
                },
                'prs_analyzed': 0,
                'critical_risk_prs': [],
                'high_risk_prs': [],
                'summary': {
                    'total_prs': 0,
                    'critical_risks': 0,
                    'high_risks': 0,
                    'risk_percentage': 0
                }
            }

        critical_prs = []
        high_prs = []
        all_risks_by_type = defaultdict(int)

        print(f"\n📊 Analyzing {len(prs)} PRs...")
        for i, pr in enumerate(prs, 1):
            print(f"  [{i}/{len(prs)}] PR #{pr['number']}: {pr['title'][:50]}...", end=' ')

            risk_data = self.analyze_pr(pr)

            # Count risk types
            for risk in risk_data['security_risks']:
                all_risks_by_type[risk['type']] += 1
            for risk in risk_data['quality_risks']:
                all_risks_by_type[risk['type']] += 1
            for risk in risk_data['test_risks']:
                all_risks_by_type[risk['type']] += 1

            if risk_data['overall_score'] >= 8.5:
                critical_prs.append(risk_data)
                print(f"🔴 CRITICAL ({risk_data['overall_score']})")
            elif risk_data['overall_score'] >= 7.0:
                high_prs.append(risk_data)
                print(f"🟠 HIGH ({risk_data['overall_score']})")
            else:
                print(f"✓ OK ({risk_data['overall_score']})")

        # Generate summary
        report = {
            'timestamp': datetime.now().isoformat(),
            'repository': self.repo,
            'date_range': {
                'from': self.date_from.isoformat(),
                'to': datetime.now().isoformat(),
                'days': self.days
            },
            'prs_analyzed': len(prs),
            'critical_risk_prs': critical_prs,
            'high_risk_prs': high_prs,
            'summary': {
                'total_prs': len(prs),
                'critical_risks': len(critical_prs),
                'high_risks': len(high_prs),
                'risk_percentage': round(
                    (len(critical_prs) + len(high_prs)) / len(prs) * 100,
                    1
                )
            },
            'risk_distribution': dict(all_risks_by_type)
        }

        return report

    def save_report(self, report: Dict, filename: str = 'pr-risk-report.json'):
        """Save report to JSON file"""
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n✓ Report saved to {filename}")

def main():
    parser = argparse.ArgumentParser(
        description='Analyze PR risks in a GitHub repository',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze-pr-risks.py --repo owner/repo --token $GITHUB_TOKEN --days 7
  python analyze-pr-risks.py --repo owner/repo --token $GITHUB_TOKEN --days 30
        """
    )
    parser.add_argument('--repo', required=True, help='GitHub repository (owner/repo)')
    parser.add_argument('--token', required=True, help='GitHub personal access token')
    parser.add_argument('--days', type=int, default=7, help='Number of days to analyze (default: 7)')

    args = parser.parse_args()

    analyzer = PRRiskAnalyzer(args.repo, args.token, args.days)
    report = analyzer.generate_report()
    analyzer.save_report(report)

    # Print summary
    print("\n" + "="*60)
    print("ANALYSIS COMPLETE")
    print("="*60)
    print(json.dumps(report['summary'], indent=2))

    return 0

if __name__ == '__main__':
    sys.exit(main())
