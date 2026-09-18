# PR Risk Analysis Pipeline Stage - Design & Implementation

## Executive Summary
Add a comprehensive risk-checking stage to your GitHub Actions pipeline that runs when a new branch is created from main. This stage analyzes all PRs merged within a configurable date range and reports security, code quality, and test-related risks.

---

## Part 1: Architecture & Design

### 1.1 High-Level Architecture

```
Pipeline Trigger: Branch created from main
    ↓
Risk Analysis Stage
    ├── Fetch PRs (date range)
    ├── Security Analysis
    │   ├── Dependency vulnerabilities (Dependabot, NuGet audit)
    │   ├── Secrets scanning
    │   └── SAST (CodeQL)
    ├── Code Quality Analysis
    │   ├── SonarQube/SonarCloud metrics
    │   ├── Code coverage trends
    │   └── Complexity metrics
    ├── Test Analysis
    │   ├── Failed test runs
    │   ├── Coverage decline
    │   └── Flaky tests
    ├── Generate Risk Report
    └── Output Summary & Artifacts
```

### 1.2 Risk Classification

**Risk Levels:**
- 🔴 **Critical**: Security vulnerabilities, failed tests in main, secrets leaked
- 🟠 **High**: Code coverage drop >5%, complex changes without review
- 🟡 **Medium**: Code quality metric decline, dependency updates
- 🟢 **Low**: Minor code style issues, documentation gaps

### 1.3 Data Collection Strategy

**Source 1: GitHub API**
- Fetch PRs using GraphQL/REST API
- Filter by date range (default: last 7 days)
- Collect: author, review status, test results, file changes

**Source 2: GitHub Check Runs**
- Query check runs attached to each PR
- Identify failed builds, tests, security scans

**Source 3: Repository Insights**
- Branch protection rules compliance
- Merge patterns and velocity

**Source 4: Integration Tools**
- SonarQube/SonarCloud for quality metrics
- Dependabot for vulnerability data
- CodeQL for SAST results

### 1.4 Risk Scoring Algorithm

```
Risk Score = (Security_Weight × Security_Risk) 
           + (Quality_Weight × Quality_Risk) 
           + (Test_Weight × Test_Risk)

Default Weights: Security=40%, Quality=35%, Test=25%

High Risk Threshold: Score ≥ 7.0/10
Critical Risk Threshold: Score ≥ 8.5/10
```

---

## Part 2: Implementation Guide

### 2.1 Prerequisites

- GitHub repository with Actions enabled
- .NET project with existing test suite
- (Optional) SonarQube/SonarCloud account
- (Recommended) Dependabot enabled
- GitHub token with repo read access

### 2.2 GitHub Actions Workflow Setup

Create `.github/workflows/pr-risk-analysis.yml`:

```yaml
name: PR Risk Analysis

on:
  create:
    branches:
      - '**'

permissions:
  contents: read
  pull-requests: read
  checks: read

jobs:
  risk-analysis:
    runs-on: ubuntu-latest
    if: github.event.ref_type == 'branch' && startsWith(github.ref, 'refs/heads/')
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Check if branch from main
        id: check-main
        run: |
          MERGE_BASE=$(git merge-base origin/main HEAD)
          CURRENT_COMMIT=$(git rev-parse HEAD)
          if [ "$MERGE_BASE" == "$CURRENT_COMMIT" ]; then
            echo "is_new_from_main=true" >> $GITHUB_OUTPUT
          else
            echo "is_new_from_main=false" >> $GITHUB_OUTPUT
          fi

      - name: Run risk analysis (if new from main)
        if: steps.check-main.outputs.is_new_from_main == 'true'
        run: |
          echo "Starting PR Risk Analysis..."
          DATE_RANGE_DAYS=7
          python $GITHUB_WORKSPACE/.github/scripts/analyze-pr-risks.py \
            --repo ${{ github.repository }} \
            --token ${{ secrets.GITHUB_TOKEN }} \
            --days $DATE_RANGE_DAYS

      - name: Upload risk report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: pr-risk-analysis-report
          path: pr-risk-report.json
          retention-days: 30

      - name: Comment PR with risk summary
        if: always() && github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = JSON.parse(fs.readFileSync('pr-risk-report.json', 'utf8'));
            const summary = buildRiskSummary(report);
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: summary
            });

      - name: Fail if critical risks found
        if: always()
        run: |
          python .github/scripts/check-risk-threshold.py
```

### 2.3 Python Risk Analysis Script

Create `.github/scripts/analyze-pr-risks.py`:

```python
#!/usr/bin/env python3
import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict
import requests

class PRRiskAnalyzer:
    def __init__(self, repo: str, token: str, days: int = 7):
        self.repo = repo
        self.token = token
        self.days = days
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = "https://api.github.com"
        self.risks = []
        self.date_from = datetime.now() - timedelta(days=days)

    def fetch_prs_in_range(self) -> List[Dict]:
        """Fetch merged PRs within the date range"""
        query = f'repo:{self.repo} is:pr is:merged merged:>={self.date_from.isoformat()}'
        url = f"{self.base_url}/search/issues?q={query}&sort=updated&order=desc&per_page=100"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json().get('items', [])

    def analyze_pr_security(self, pr: Dict) -> Dict:
        """Analyze security risks in a PR"""
        risk_data = {
            'number': pr['number'],
            'title': pr['title'],
            'author': pr['user']['login'],
            'merged_at': pr['merged_at'],
            'security_risks': [],
            'quality_risks': [],
            'test_risks': [],
            'overall_score': 0
        }

        # Get PR details including reviews
        pr_url = pr['url']
        pr_detail = requests.get(pr_url, headers=self.headers).json()

        # Check: Number of reviewers
        reviews_url = f"{pr_url}/reviews"
        reviews = requests.get(reviews_url, headers=self.headers).json()
        if len(reviews) < 2:
            risk_data['security_risks'].append({
                'type': 'insufficient_review',
                'severity': 'high',
                'message': f'Only {len(reviews)} reviewer(s) - consider requiring 2+ approvals'
            })

        # Check: Files changed count
        files_url = f"{pr_url}/files"
        files = requests.get(files_url, headers=self.headers).json()
        if len(files) > 50:
            risk_data['security_risks'].append({
                'type': 'large_changeset',
                'severity': 'medium',
                'message': f'{len(files)} files changed - large PRs increase risk'
            })

        # Check: Sensitive file changes
        sensitive_patterns = ['.env', 'config', 'credentials', 'secret', 'password', 'token']
        for file in files:
            if any(pattern in file.get('filename', '').lower() for pattern in sensitive_patterns):
                risk_data['security_risks'].append({
                    'type': 'sensitive_file_change',
                    'severity': 'critical',
                    'message': f'Sensitive file modified: {file["filename"]}'
                })

        # Check: Merged without approval
        approved = any(r['state'] == 'APPROVED' for r in reviews)
        if not approved:
            risk_data['security_risks'].append({
                'type': 'no_approval',
                'severity': 'critical',
                'message': 'PR merged without explicit approval'
            })

        return risk_data

    def analyze_pr_quality(self, pr: Dict) -> Dict:
        """Analyze code quality metrics"""
        quality_risks = []

        # Get check runs (includes SonarQube, Code coverage, etc.)
        pr_url = pr['url']
        statuses_url = f"{pr_url}/commits/{pr['merge_commit_sha']}/check-runs"
        
        try:
            response = requests.get(statuses_url, headers=self.headers)
            if response.status_code == 200:
                checks = response.json().get('check_runs', [])
                
                for check in checks:
                    if check['status'] == 'completed':
                        if check['conclusion'] == 'failure':
                            quality_risks.append({
                                'type': 'check_failed',
                                'severity': 'high',
                                'message': f'Check failed: {check["name"]}'
                            })
                        
                        # Parse SonarQube if present
                        if 'sonar' in check['name'].lower():
                            if check['output'].get('summary'):
                                quality_risks.append({
                                    'type': 'code_quality_issue',
                                    'severity': 'medium',
                                    'message': check['output']['summary']
                                })
        except Exception as e:
            print(f"Error fetching checks for PR #{pr['number']}: {e}")

        return quality_risks

    def analyze_pr_tests(self, pr: Dict) -> Dict:
        """Analyze test-related risks"""
        test_risks = []
        
        # Get status checks (older API, includes tests)
        statuses_url = f"{self.base_url}/repos/{self.repo}/commits/{pr['merge_commit_sha']}/status"
        
        try:
            response = requests.get(statuses_url, headers=self.headers)
            if response.status_code == 200:
                status = response.json()
                if status['state'] == 'failure':
                    test_risks.append({
                        'type': 'test_failure',
                        'severity': 'critical',
                        'message': 'Tests failed but PR was merged'
                    })
                
                # Analyze individual statuses
                for check in status.get('statuses', []):
                    if 'test' in check['context'].lower() and check['state'] == 'failure':
                        test_risks.append({
                            'type': 'test_failure',
                            'severity': 'critical',
                            'message': f'{check["context"]} failed'
                        })
        except Exception as e:
            print(f"Error fetching tests for PR #{pr['number']}: {e}")

        return test_risks

    def calculate_risk_score(self, risk_data: Dict) -> float:
        """Calculate overall risk score (0-10)"""
        security_weight = 0.40
        quality_weight = 0.35
        test_weight = 0.25
        
        security_score = len(risk_data['security_risks']) * 2  # Max ~10
        quality_score = len(risk_data['quality_risks']) * 1.5  # Max ~10
        test_score = len(risk_data['test_risks']) * 3  # Tests weighted heavily
        
        overall = (
            min(security_score, 10) * security_weight +
            min(quality_score, 10) * quality_weight +
            min(test_score, 10) * test_weight
        )
        
        return min(overall, 10.0)

    def generate_report(self) -> Dict:
        """Generate comprehensive risk report"""
        prs = self.fetch_prs_in_range()
        report = {
            'timestamp': datetime.now().isoformat(),
            'repository': self.repo,
            'date_range': {
                'from': self.date_from.isoformat(),
                'to': datetime.now().isoformat(),
                'days': self.days
            },
            'prs_analyzed': len(prs),
            'high_risk_prs': [],
            'critical_risk_prs': [],
            'summary': {}
        }

        for pr in prs:
            risk_data = self.analyze_pr_security(pr)
            risk_data['quality_risks'] = self.analyze_pr_quality(pr)
            risk_data['test_risks'] = self.analyze_pr_tests(pr)
            
            risk_data['overall_score'] = self.calculate_risk_score(risk_data)
            
            if risk_data['overall_score'] >= 8.5:
                report['critical_risk_prs'].append(risk_data)
            elif risk_data['overall_score'] >= 7.0:
                report['high_risk_prs'].append(risk_data)

        # Generate summary
        report['summary'] = {
            'total_prs': len(prs),
            'critical_risks': len(report['critical_risk_prs']),
            'high_risks': len(report['high_risk_prs']),
            'risk_percentage': round(
                (len(report['critical_risk_prs']) + len(report['high_risk_prs'])) / len(prs) * 100,
                1
            ) if prs else 0
        }

        return report

    def save_report(self, report: Dict, filename: str = 'pr-risk-report.json'):
        """Save report to file"""
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description='Analyze PR risks')
    parser.add_argument('--repo', required=True, help='GitHub repository (owner/repo)')
    parser.add_argument('--token', required=True, help='GitHub token')
    parser.add_argument('--days', type=int, default=7, help='Number of days to analyze')
    
    args = parser.parse_args()
    
    analyzer = PRRiskAnalyzer(args.repo, args.token, args.days)
    report = analyzer.generate_report()
    analyzer.save_report(report)
    
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
```

### 2.4 Risk Threshold Check Script

Create `.github/scripts/check-risk-threshold.py`:

```python
#!/usr/bin/env python3
import json
import sys

def check_thresholds():
    with open('pr-risk-report.json', 'r') as f:
        report = json.load(f)
    
    summary = report.get('summary', {})
    critical_risks = summary.get('critical_risks', 0)
    high_risks = summary.get('high_risks', 0)
    risk_percentage = summary.get('risk_percentage', 0)
    
    print("=" * 60)
    print("PR RISK ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"PRs Analyzed: {summary.get('total_prs', 0)}")
    print(f"Critical Risks: {critical_risks}")
    print(f"High Risks: {high_risks}")
    print(f"Risk Percentage: {risk_percentage}%")
    print("=" * 60)
    
    # Define thresholds
    CRITICAL_THRESHOLD = 2  # Fail if 2+ critical risks
    HIGH_THRESHOLD = 5      # Warn if 5+ high risks
    RISK_PCT_THRESHOLD = 30  # Fail if >30% PRs are risky
    
    exit_code = 0
    
    if critical_risks >= CRITICAL_THRESHOLD:
        print(f"❌ CRITICAL: Found {critical_risks} critical risk(s)")
        exit_code = 1
    
    if high_risks >= HIGH_THRESHOLD:
        print(f"⚠️  WARNING: Found {high_risks} high risk(s)")
        # Don't fail, just warn
    
    if risk_percentage > RISK_PCT_THRESHOLD:
        print(f"❌ CRITICAL: {risk_percentage}% of PRs are risky (threshold: {RISK_PCT_THRESHOLD}%)")
        exit_code = 1
    
    if exit_code == 0:
        print("✅ Risk analysis passed")
    
    sys.exit(exit_code)

if __name__ == '__main__':
    check_thresholds()
```

### 2.5 GitHub Actions Summary Output

Add to your workflow to display risk summary:

```yaml
      - name: Create risk summary
        if: always()
        run: |
          python .github/scripts/generate-summary.py >> $GITHUB_STEP_SUMMARY
```

Create `.github/scripts/generate-summary.py`:

```python
#!/usr/bin/env python3
import json

with open('pr-risk-report.json', 'r') as f:
    report = json.load(f)

summary = report['summary']

markdown = f"""
## 📊 PR Risk Analysis Report

| Metric | Value |
|--------|-------|
| Total PRs Analyzed | {summary['total_prs']} |
| Critical Risks | 🔴 {summary['critical_risks']} |
| High Risks | 🟠 {summary['high_risks']} |
| Risk Percentage | {summary['risk_percentage']}% |

"""

if report['critical_risk_prs']:
    markdown += "### 🔴 Critical Risk PRs\n"
    for pr in report['critical_risk_prs']:
        markdown += f"- **#{pr['number']}** ({pr['author']}) - Score: {pr['overall_score']:.1f}/10\n"

if report['high_risk_prs']:
    markdown += "### 🟠 High Risk PRs\n"
    for pr in report['high_risk_prs']:
        markdown += f"- **#{pr['number']}** ({pr['author']}) - Score: {pr['overall_score']:.1f}/10\n"

print(markdown)
```

---

## Part 3: Advanced Enhancements

### 3.1 Integration with SonarQube

```yaml
      - name: Run SonarQube analysis
        uses: SonarSource/sonarcloud-github-action@master
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

### 3.2 Dependabot Integration

Enable in Settings → Security & Analysis → Dependabot to automatically flag vulnerable dependencies.

### 3.3 CodeQL for SAST

```yaml
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v2
        with:
          languages: 'csharp'
      
      - name: Autobuild
        uses: github/codeql-action/autobuild@v2
      
      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v2
```

---

## Part 4: Configuration & Customization

### 4.1 Key Configuration Points

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DAYS` | 7 | Number of days to analyze |
| `CRITICAL_THRESHOLD` | 2 | Fail if ≥ critical risks |
| `HIGH_THRESHOLD` | 5 | Warn if ≥ high risks |
| `RISK_PCT_THRESHOLD` | 30% | Fail if risk % exceeds |
| `MIN_REVIEWERS` | 2 | Minimum required reviewers |
| `MAX_FILES_CHANGE` | 50 | Large changeset threshold |

### 4.2 Sensitive File Patterns

Customize in `analyze-pr-risks.py`:

```python
sensitive_patterns = [
    '.env', 'config', 'credentials', 'secret', 
    'password', 'token', 'key', 'apikey', 'connectionstring'
]
```

---

## Part 5: Deployment Steps

1. **Create workflow file**: `.github/workflows/pr-risk-analysis.yml`
2. **Create scripts directory**: `.github/scripts/`
3. **Add Python scripts** to scripts directory
4. **Test with a test branch**: Create a branch from main to trigger
5. **Review reports**: Check "Actions" tab for results
6. **Adjust thresholds** based on your team's tolerance
7. **Document** custom rules in team wiki

---

## Part 6: Monitoring & Reporting

### Real-time Dashboards
- GitHub Actions run history
- Artifact storage (30-day retention)
- Email notifications on critical risks

### Weekly Reports
Schedule a report generation:

```yaml
schedule:
  - cron: '0 9 * * 1'  # Every Monday at 9 AM
```

### Metrics to Track
- Risk trend (↑ vs ↓)
- Common risk types
- Authors with most risks
- PR review velocity

---

## Summary

This design provides:
✅ Automated risk detection across 3 categories  
✅ Configurable thresholds and rules  
✅ Clear visibility into problematic PRs  
✅ Integration with GitHub ecosystem  
✅ Actionable risk reporting  
✅ Fail gates for critical risks  

Start with the core implementation and add tool integrations (SonarQube, CodeQL) as needed.
