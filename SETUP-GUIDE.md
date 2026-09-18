# PR Risk Analysis - Setup & Deployment Guide

## Quick Start (5 minutes)

### Step 1: Create Directory Structure

In your repository root, create these directories:

```bash
mkdir -p .github/scripts
```

### Step 2: Add Files to Your Repository

Copy these files to your repository:

```
your-repo/
├── .github/
│   ├── workflows/
│   │   └── pr-risk-analysis.yml          # Main workflow
│   └── scripts/
│       ├── analyze-pr-risks.py           # Risk analysis engine
│       ├── check-risk-threshold.py       # Threshold validation
│       └── generate-summary.py           # GitHub Actions summary
```

**Copy commands:**
```bash
# Copy workflow file
cp pr-risk-analysis.yml your-repo/.github/workflows/

# Copy Python scripts
cp analyze-pr-risks.py your-repo/.github/scripts/
cp check-risk-threshold.py your-repo/.github/scripts/
cp generate-summary.py your-repo/.github/scripts/

# Make scripts executable (optional but recommended)
chmod +x your-repo/.github/scripts/*.py
```

### Step 3: Commit and Push

```bash
git add .github/
git commit -m "chore: add PR risk analysis pipeline stage"
git push origin main
```

### Step 4: Test the Pipeline

Create a test branch from main:

```bash
git checkout main
git pull
git checkout -b test/risk-analysis-setup
git push origin test/risk-analysis-setup
```

The pipeline should automatically trigger. Check:
- **GitHub Actions tab** → Look for "PR Risk Analysis" workflow
- **Artifacts** → Download `pr-risk-analysis-report` to see the JSON report

---

## Configuration Guide

### Adjusting Risk Thresholds

Edit `check-risk-threshold.py` to customize thresholds:

```python
# Line ~45 - Adjust these values
CRITICAL_THRESHOLD = 1        # How many critical PRs to fail on
HIGH_THRESHOLD = 3             # How many high PRs to warn on
RISK_PCT_THRESHOLD = 25        # What % of PRs being risky = fail
```

**Examples:**
- Strict: `CRITICAL_THRESHOLD = 0, RISK_PCT_THRESHOLD = 10`
- Relaxed: `CRITICAL_THRESHOLD = 3, RISK_PCT_THRESHOLD = 40`

### Adjusting Analysis Period

Edit `pr-risk-analysis.yml`:

```yaml
      - name: Run PR Risk Analysis
        env:
          ANALYSIS_DAYS: 7      # Change this number
```

Options:
- `7` = Last 7 days (default, weekly check)
- `30` = Last 30 days (monthly review)
- `1` = Since yesterday

### Adjusting Sensitive File Patterns

Edit `analyze-pr-risks.py` line ~36:

```python
self.sensitive_patterns = [
    '.env',                  # Add your patterns here
    'config',
    'credentials',
    'appsettings.json',      # .NET specific
    'secrets.json',          # .NET specific
    'your-pattern-here'      # Add more as needed
]
```

### Adjusting Review Requirements

Edit `analyze-pr-risks.py` line ~35:

```python
self.min_reviewers = 2       # Require 2 minimum reviewers
self.max_files_change = 50   # Flag PRs changing 50+ files
```

---

## Understanding the Report

### Report Structure

The JSON report (`pr-risk-report.json`) contains:

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "repository": "owner/repo",
  "prs_analyzed": 12,
  "summary": {
    "total_prs": 12,
    "critical_risks": 1,
    "high_risks": 2,
    "risk_percentage": 25.0
  },
  "critical_risk_prs": [
    {
      "number": 123,
      "title": "Add authentication",
      "author": "john-doe",
      "overall_score": 8.7,
      "security_risks": [
        {
          "type": "sensitive_file_change",
          "severity": "critical",
          "message": "Sensitive file modified: appsettings.json"
        }
      ],
      "test_risks": [],
      "quality_risks": []
    }
  ],
  "high_risk_prs": [],
  "risk_distribution": {
    "insufficient_review": 2,
    "large_changeset": 1
  }
}
```

### Risk Score Calculation

```
Risk Score = (Security_Weight × Security_Score) 
           + (Quality_Weight × Quality_Score) 
           + (Test_Weight × Test_Score)

Where:
- Security_Weight = 40%
- Quality_Weight = 35%
- Test_Weight = 25%

Score ranges:
- 0-3: Low Risk (🟢)
- 3-7: High Risk (🟠)
- 7-10: Critical Risk (🔴)
```

### Risk Types

**Security Risks:**
- `sensitive_file_change` - Credentials, secrets, configs modified
- `insufficient_review` - Fewer than required reviewers
- `no_approval` - Merged without explicit approval
- `large_changeset` - Too many files changed
- `concerning_comments` - Comments mention security/bugs

**Quality Risks:**
- `check_failed` - Build/lint checks failed
- `sonar_quality_gate_failed` - Code quality metrics not met
- `coverage_insufficient` - Test coverage below threshold
- `commit_status_failed` - Commit status check failed

**Test Risks:**
- `test_failure` - Tests failed but PR merged
- `test_skipped` - Test runs were skipped

---

## Advanced Usage

### Running Locally

Test the analyzer on your machine:

```bash
# Install dependencies
pip install requests

# Run analysis
python analyze-pr-risks.py \
  --repo "your-org/your-repo" \
  --token "ghp_your_token_here" \
  --days 7
```

**Note**: You need a GitHub Personal Access Token with `repo:read` permissions.

**Getting a token:**
1. Go to GitHub.com → Settings → Developer settings → Personal access tokens
2. Click "Generate new token"
3. Select scope: `public_repo` or `repo` (private repos)
4. Copy the token (you'll only see it once)

### Scheduling Regular Reports

Edit `pr-risk-analysis.yml` to run on a schedule:

```yaml
on:
  create:
    branches:
      - '**'
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM UTC
    # - cron: '0 9 * * *'  # Every day at 9 AM UTC
```

### Integration with Slack

Add to `pr-risk-analysis.yml` to notify Slack on critical risks:

```yaml
      - name: Notify Slack on critical risks
        if: failure()
        uses: slackapi/slack-github-action@v1.24.0
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {
              "text": "🔴 Critical PR Risks Detected",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "Critical risks found in recent PRs. Check the full report: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
                  }
                }
              ]
            }
```

**Setup:**
1. Create a Slack incoming webhook: https://api.slack.com/messaging/webhooks
2. Add the webhook URL as a GitHub secret: `SLACK_WEBHOOK`

### Integration with Email

Use GitHub's built-in email notifications or add a custom action:

```yaml
      - name: Send email on critical risks
        if: failure()
        uses: dawidd6/action-send-mail@v3
        with:
          server_address: ${{ secrets.MAIL_SERVER }}
          server_port: ${{ secrets.MAIL_PORT }}
          username: ${{ secrets.MAIL_USERNAME }}
          password: ${{ secrets.MAIL_PASSWORD }}
          subject: '🔴 Critical PR Risks Detected in ${{ github.repository }}'
          to: security-team@company.com
          from: github-actions@company.com
          body: |
            Critical PR risks detected in the last analysis.
            
            Repository: ${{ github.repository }}
            Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
            
            Check the full report in the artifacts.
```

---

## Troubleshooting

### "No PRs found in date range"

**Cause**: No merged PRs in the specified date range

**Solution**:
- Increase `ANALYSIS_DAYS` in the workflow
- Check that PRs are actually being merged (not just created)

### "Error fetching PRs: 401 Unauthorized"

**Cause**: GitHub token is invalid or expired

**Solution**:
- Verify the token has proper permissions
- Check that it hasn't expired
- GitHub Actions automatically provides `GITHUB_TOKEN` in the workflow, so this shouldn't happen unless you're running locally

### "No module named requests"

**Cause**: Python dependencies not installed

**Solution**: The workflow installs dependencies automatically. If running locally:
```bash
pip install requests
```

### Workflow not triggering

**Cause**: Event filter not matching

**Solution**:
1. Verify you're creating a NEW branch from main
2. Check that the branch matches the pattern (should match all with `**`)
3. View Actions tab to see if the workflow appears

### "SyntaxError in Python script"

**Cause**: File encoding or line ending issues during copy

**Solution**:
```bash
# Re-clone the files or ensure Unix line endings
dos2unix .github/scripts/*.py  # On macOS/Linux
# Or in the repo, set core.autocrlf:
git config core.autocrlf true
```

---

## Best Practices

### 1. Review Critical Risks Immediately
Set up Slack/email notifications so your team knows immediately when critical risks are found.

### 2. Adjust Thresholds Gradually
Start with relaxed thresholds, then tighten over time as your team improves practices.

### 3. Fix Root Causes
Use the risk data to identify patterns:
- Specific file types always flagged?
- Certain authors have lower review counts?
- Particular check runs frequently failing?

### 4. Regular Reviews
Review the weekly reports to identify trends and adjust processes.

### 5. Communicate with Team
Share reports with the team and discuss what risks mean for your project.

---

## Example Output

When the workflow runs successfully, you'll see:

**In GitHub Actions tab:**
```
✅ Risk Analysis
  ✓ Check if branch created from main (2s)
  ✓ Set up Python (1s)
  ✓ Install dependencies (3s)
  ✓ Run PR Risk Analysis (15s)
  ✓ Check risk thresholds (2s)
  ✓ Generate summary for GitHub Actions (1s)
  ✓ Upload risk report artifact (1s)
```

**In the Step Summary:**
```
🟢 PR Risk Analysis Report

Status: RISKS WITHIN LIMITS

Summary Metrics

| Metric | Count | Threshold |
|--------|-------|-----------|
| Total PRs Analyzed | 12 | - |
| Critical Risk PRs | 0 | ≥ 1 ❌ |
| High Risk PRs | 1 | ≥ 3 ⚠️ |
| Risk Percentage | 8.3% | > 25% ❌ |

✅ Risk analysis PASSED
```

---

## Support & Maintenance

### Version Updates

The scripts are designed to work with the GitHub API v3. Updates may be needed if GitHub changes their API.

### Adding More Risk Types

To add custom risk detection:

1. Add a new method to `PRRiskAnalyzer` class in `analyze-pr-risks.py`
2. Call it from the `analyze_pr()` method
3. Return a list of risk dictionaries
4. The risk score calculation will automatically weight it

Example:
```python
def analyze_pr_deployment(self, pr: Dict) -> List:
    """Check for deployment-related risks"""
    risks = []
    # Your custom logic here
    return risks
```

### Performance Optimization

For repos with 100+ PRs per week:
- Reduce `ANALYSIS_DAYS` to 3-5
- Or increase server resources for Actions runner
- Consider caching API responses between runs

---

## Questions?

For issues or questions:
1. Check the Troubleshooting section above
2. Review the design document: `PR-Risk-Analysis-Design.md`
3. Check GitHub Actions logs for detailed error messages
4. Review GitHub API documentation: https://docs.github.com/en/rest

---

**Last Updated**: January 2024  
**Compatible With**: GitHub Actions, .NET/C# projects, any language  
**License**: MIT
