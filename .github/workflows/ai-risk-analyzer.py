#!/usr/bin/env python3
"""
AI-Powered PR Risk Analyzer - Uses Claude API for intelligent risk detection
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Optional
import requests
from datetime import datetime
import anthropic

class AIRiskAnalyzer:
    """Uses Claude AI to analyze PRs for intelligent risk detection"""

    def __init__(self, github_token: str, claude_api_key: str, repo: str, days: int = 7):
        self.github_token = github_token
        self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
        self.repo = repo
        self.days = days
        self.github_headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.github_base_url = "https://api.github.com"
        self.max_diff_size = 10000  # Limit diff size to keep API calls reasonable

    def fetch_prs_in_range(self) -> List[Dict]:
        """Fetch recent merged PRs"""
        from datetime import datetime, timedelta
        date_from = datetime.now() - timedelta(days=self.days)
        date_from_str = date_from.isoformat().split('T')[0]

        query = f'repo:{self.repo} is:pr is:merged merged:>={date_from_str}'
        url = f"{self.github_base_url}/search/issues"
        params = {
            'q': query,
            'sort': 'updated',
            'order': 'desc',
            'per_page': 50
        }

        try:
            response = requests.get(url, headers=self.github_headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json().get('items', [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching PRs: {e}")
            return []

    def get_pr_diff(self, pr_number: int) -> Optional[str]:
        """Fetch the diff/patch for a PR"""
        try:
            url = f"{self.github_base_url}/repos/{self.repo}/pulls/{pr_number}"
            response = requests.get(url, headers=self.github_headers, timeout=10)
            response.raise_for_status()

            pr_data = response.json()
            diff_url = pr_data['diff_url']

            diff_response = requests.get(diff_url, headers=self.github_headers, timeout=10)
            diff_response.raise_for_status()

            diff_text = diff_response.text
            # Limit diff size to keep API costs reasonable
            if len(diff_text) > self.max_diff_size:
                diff_text = diff_text[:self.max_diff_size] + "\n... (truncated)"

            return diff_text
        except Exception as e:
            print(f"⚠️  Could not fetch diff for PR #{pr_number}: {e}")
            return None

    def get_pr_files(self, pr_number: int) -> List[Dict]:
        """Get files changed in a PR"""
        try:
            url = f"{self.github_base_url}/repos/{self.repo}/pulls/{pr_number}/files"
            response = requests.get(url, headers=self.github_headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️  Could not fetch files for PR #{pr_number}: {e}")
            return []

    def get_pr_reviews(self, pr_number: int) -> List[Dict]:
        """Get reviews for a PR"""
        try:
            url = f"{self.github_base_url}/repos/{self.repo}/pulls/{pr_number}/reviews"
            response = requests.get(url, headers=self.github_headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️  Could not fetch reviews for PR #{pr_number}: {e}")
            return []

    def analyze_pr_with_ai(self, pr: Dict) -> Dict:
        """Use Claude API to intelligently analyze a PR for risks"""

        pr_number = pr['number']
        print(f"  🤖 AI analyzing PR #{pr_number}...", end=" ", flush=True)

        try:
            # Gather PR information
            diff = self.get_pr_diff(pr_number)
            files = self.get_pr_files(pr_number)
            reviews = self.get_pr_reviews(pr_number)

            # Prepare context for Claude
            file_summary = f"Files changed: {len(files)}\n"
            for file in files[:10]:  # Show top 10 files
                file_summary += f"  - {file['filename']} (+{file.get('additions', 0)} -{file.get('deletions', 0)})\n"

            review_summary = f"Reviews: {len(reviews)}\n"
            approvals = [r for r in reviews if r['state'] == 'APPROVED']
            review_summary += f"  - Approved: {len(approvals)}\n"

            # Create the analysis prompt
            analysis_prompt = f"""
You are a security and code quality expert. Analyze this GitHub PR for potential risks.

**PR Details:**
- Title: {pr['title']}
- Author: {pr['user']['login']}
- Number: {pr_number}
- URL: {pr['html_url']}
- Description: {pr.get('body', 'No description provided')[:500]}

**Files Changed:**
{file_summary}

**Review Status:**
{review_summary}

**Code Changes (Diff):**
```
{diff if diff else "Could not fetch diff"}
```

**Analyze for:**
1. **Security Risks**: Look for potential vulnerabilities, credential exposure, unsafe patterns, authentication/authorization issues
2. **Code Quality**: Check for maintainability issues, complexity, best practices violations, potential bugs
3. **Architecture**: Identify any architectural concerns or design issues
4. **Testing**: Are there test additions for new code? Is coverage adequate?
5. **Performance**: Any potential performance issues or bottlenecks?

**Response Format:**
Return a JSON object with this structure:
{{
    "severity": "critical|high|medium|low",
    "ai_insights": [
        {{
            "category": "security|quality|architecture|testing|performance",
            "issue": "description of the issue",
            "severity": "critical|high|medium|low",
            "recommendation": "how to fix it"
        }}
    ],
    "overall_assessment": "brief summary of risks found",
    "confidence": 0.0-1.0
}}

Be specific and actionable. If no significant issues found, return empty ai_insights array.
"""

            # Call Claude API
            message = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[
                    {"role": "user", "content": analysis_prompt}
                ]
            )

            # Parse response
            response_text = message.content[0].text

            # Try to extract JSON from response
            try:
                # Find JSON in the response
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    ai_analysis = json.loads(json_match.group())
                else:
                    ai_analysis = {
                        "severity": "medium",
                        "ai_insights": [],
                        "overall_assessment": response_text,
                        "confidence": 0.5
                    }
            except json.JSONDecodeError:
                ai_analysis = {
                    "severity": "medium",
                    "ai_insights": [],
                    "overall_assessment": response_text,
                    "confidence": 0.5
                }

            print(f"✓ ({ai_analysis['severity'].upper()})")
            return ai_analysis

        except anthropic.APIError as e:
            print(f"❌ AI API error: {e}")
            return {
                "severity": "unknown",
                "ai_insights": [],
                "overall_assessment": f"AI analysis failed: {str(e)}",
                "confidence": 0.0
            }
        except Exception as e:
            print(f"❌ Error: {e}")
            return {
                "severity": "unknown",
                "ai_insights": [],
                "overall_assessment": f"Analysis failed: {str(e)}",
                "confidence": 0.0
            }

    def calculate_ai_risk_score(self, ai_analysis: Dict) -> float:
        """Convert AI severity to a risk score (0-10)"""
        severity_map = {
            "critical": 9.0,
            "high": 7.0,
            "medium": 5.0,
            "low": 2.0,
            "unknown": 5.0
        }

        base_score = severity_map.get(ai_analysis.get('severity', 'unknown'), 5.0)
        confidence = ai_analysis.get('confidence', 0.0)

        # Adjust score based on confidence
        adjusted_score = base_score * confidence + (5.0 * (1 - confidence))

        return min(adjusted_score, 10.0)

    def generate_report(self) -> Dict:
        """Generate AI-enhanced risk report"""
        print("\n" + "="*70)
        print("AI-POWERED PR RISK ANALYSIS")
        print("="*70)

        prs = self.fetch_prs_in_range()

        if not prs:
            print("⚠️  No PRs found")
            return self._empty_report()

        print(f"\n📊 Analyzing {len(prs)} PRs with Claude AI...")

        critical_prs = []
        high_prs = []
        medium_prs = []

        for i, pr in enumerate(prs, 1):
            pr_number = pr['number']
            title = pr['title'][:40]

            # AI analysis
            ai_analysis = self.analyze_pr_with_ai(pr)
            ai_score = self.calculate_ai_risk_score(ai_analysis)

            pr_risk = {
                'number': pr_number,
                'title': pr['title'],
                'author': pr['user']['login'],
                'url': pr['html_url'],
                'merged_at': pr['merged_at'],
                'ai_analysis': ai_analysis,
                'ai_risk_score': round(ai_score, 1)
            }

            if ai_score >= 8.0:
                critical_prs.append(pr_risk)
            elif ai_score >= 6.5:
                high_prs.append(pr_risk)
            else:
                medium_prs.append(pr_risk)

        report = {
            'timestamp': datetime.now().isoformat(),
            'repository': self.repo,
            'analysis_type': 'AI-Powered',
            'ai_model': 'Claude 3.5 Sonnet',
            'prs_analyzed': len(prs),
            'critical_risk_prs': critical_prs,
            'high_risk_prs': high_prs,
            'medium_risk_prs': medium_prs,
            'summary': {
                'total_prs': len(prs),
                'critical_risks': len(critical_prs),
                'high_risks': len(high_prs),
                'medium_risks': len(medium_prs),
                'risk_percentage': round(
                    (len(critical_prs) + len(high_prs)) / len(prs) * 100,
                    1
                ) if prs else 0
            }
        }

        return report

    def _empty_report(self) -> Dict:
        """Return empty report template"""
        return {
            'timestamp': datetime.now().isoformat(),
            'repository': self.repo,
            'analysis_type': 'AI-Powered',
            'ai_model': 'Claude 3.5 Sonnet',
            'prs_analyzed': 0,
            'critical_risk_prs': [],
            'high_risk_prs': [],
            'medium_risk_prs': [],
            'summary': {
                'total_prs': 0,
                'critical_risks': 0,
                'high_risks': 0,
                'medium_risks': 0,
                'risk_percentage': 0
            }
        }

    def save_report(self, report: Dict, filename: str = 'pr-risk-report-ai.json'):
        """Save report to JSON"""
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n✓ Report saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description='AI-powered PR risk analysis')
    parser.add_argument('--repo', required=True, help='GitHub repo (owner/repo)')
    parser.add_argument('--github-token', required=True, help='GitHub token')
    parser.add_argument('--claude-token', required=True, help='Anthropic API key')
    parser.add_argument('--days', type=int, default=7, help='Days to analyze')

    args = parser.parse_args()

    analyzer = AIRiskAnalyzer(
        args.github_token,
        args.claude_token,
        args.repo,
        args.days
    )
    report = analyzer.generate_report()
    analyzer.save_report(report)

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print(json.dumps(report['summary'], indent=2))

if __name__ == '__main__':
    sys.exit(main())
