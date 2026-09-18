# AI-Powered PR Risk Analysis - Complete Setup Guide

## Overview

This guide covers setting up Claude AI-powered PR risk analysis in your GitHub Actions pipeline. The AI analyzer understands code context, detects subtle vulnerabilities, and identifies architectural issues that rule-based systems miss.

---

## Part 1: Prerequisites & Setup

### 1.1 Get Anthropic API Key

1. Sign up at **https://console.anthropic.com**
2. Go to **Settings → API Keys**
3. Create a new API key
4. Copy the key (you'll only see it once)

### 1.2 Add API Key to GitHub Secrets

1. Go to your repository: **Settings → Secrets and variables → Actions**
2. Click **"New repository secret"**
3. Name: `ANTHROPIC_API_KEY`
4. Value: Paste your Anthropic API key
5. Click **"Add secret"**

### 1.3 Verify GitHub Token

GitHub Actions automatically provides `GITHUB_TOKEN` - no setup needed.

---

## Part 2: Installation

### Step 1: Create Directory Structure

```bash
mkdir -p .github/workflows
mkdir -p .github/scripts
```

### Step 2: Add Workflow File

Copy `pr-risk-analysis-ai.yml` to `.github/workflows/`

```bash
cp pr-risk-analysis-ai.yml .github/workflows/
```

### Step 3: Add Python Scripts

Copy all AI analysis scripts to `.github/scripts/`:

```bash
cp ai-risk-analyzer.py .github/scripts/
cp check-ai-risk-threshold.py .github/scripts/
cp generate-ai-summary.py .github/scripts/
```

### Step 4: Update Dependencies

The workflow automatically installs `anthropic` package. No additional setup needed.

### Step 5: Commit & Test

```bash
git add .github/
git commit -m "feat: add AI-powered PR risk analysis"
git push origin main

# Create a test branch from main
git checkout -b test/ai-analysis
git push origin test/ai-analysis
```

---

## Part 3: How It Works

### 3.1 Analysis Flow

```
Branch Created from Main
         ↓
GitHub Workflow Triggered
         ↓
Fetch Recent Merged PRs
         ↓
For Each PR:
  ├── Fetch code diff
  ├── Fetch file changes
  ├── Fetch review status
  ├── Send to Claude API with context
  └── Claude returns risk analysis
         ↓
Aggregate Results
         ↓
Generate Report & Summary
         ↓
Check Thresholds
         ↓
Report Results
```

### 3.2 What Claude AI Analyzes

**Security**
- Credential exposure in code
- Unsafe authentication patterns
- SQL injection vulnerabilities
- Unvalidated input handling
- Cryptographic weaknesses

**Code Quality**
- Maintainability issues
- Code complexity
- Lack of error handling
- Best practices violations
- Design anti-patterns

**Architecture**
- Architectural consistency
- Dependency issues
- Scalability concerns
- Performance problems
- Breaking API changes

**Testing**
- Test coverage for new code
- Test quality
- Edge case coverage
- Integration test gaps

**Performance**
- N+1 query problems
- Memory leaks
- Inefficient algorithms
- Resource exhaustion risks

---

## Part 4: Configuration

### 4.1 Adjust Analysis Period

Edit `.github/workflows/pr-risk-analysis-ai.yml`:

```yaml
env:
  ANALYSIS_DAYS: 7  # Change this number
```

Options:
- `1` - Last 24 hours
- `7` - Last 7 days (default, weekly)
- `30` - Last 30 days (monthly)

### 4.2 Adjust Risk Thresholds

Edit `.github/scripts/check-ai-risk-threshold.py` around line 35:

```python
CRITICAL_THRESHOLD = 0        # How many critical PRs allowed
HIGH_THRESHOLD = 2             # How many high PRs to warn on
MEDIUM_THRESHOLD = 5           # Max medium-risk PRs
```

**Recommendation**: Start strict, relax gradually as team improves.

### 4.3 Customize AI Prompt

Edit `.github/scripts/ai-risk-analyzer.py` around line 130 in the `analysis_prompt`:

```python
analysis_prompt = f"""
You are a security and code quality expert. Analyze this GitHub PR for potential risks.

[... customize the analysis instructions ...]
"""
```

### 4.4 Set Diff Size Limit

Edit line 25 in `ai-risk-analyzer.py`:

```python
self.max_diff_size = 10000  # Bytes - increase for detailed analysis, decrease for cost
```

---

## Part 5: Understanding AI Reports

### 5.1 Risk Scoring

AI Risk Score = `Base Severity Score × Confidence Level`

- **Base Score**: Critical(9), High(7), Medium(5), Low(2)
- **Confidence**: 0.0-1.0 based on AI analysis certainty
- **Final Score**: 0-10 (higher = riskier)

Ranges:
- 0-3: Low Risk 🟢
- 3-7: High Risk 🟠
- 7-10: Critical Risk 🔴

### 5.2 Report Structure

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "repository": "owner/repo",
  "ai_model": "Claude 3.5 Sonnet",
  "analysis_type": "AI-Powered",
  "prs_analyzed": 5,
  "critical_risk_prs": [
    {
      "number": 123,
      "title": "Add authentication",
      "ai_risk_score": 8.5,
      "ai_analysis": {
        "severity": "critical",
        "overall_assessment": "...",
        "confidence": 0.95,
        "ai_insights": [
          {
            "category": "security",
            "issue": "Hardcoded credentials detected",
            "severity": "critical",
            "recommendation": "Use environment variables or secret management"
          }
        ]
      }
    }
  ],
  "summary": {
    "total_prs": 5,
    "critical_risks": 1,
    "high_risks": 1,
    "medium_risks": 2
  }
}
```

### 5.3 AI Categories

**Security** - Code-level security issues  
**Quality** - Maintainability and best practices  
**Architecture** - System design concerns  
**Testing** - Test coverage gaps  
**Performance** - Speed and resource issues  

---

## Part 6: Cost Management

### 6.1 Pricing

Claude API usage:
- **Input**: $3 per 1M tokens (~750K words)
- **Output**: $15 per 1M tokens (~750K words)

**Cost per PR Analysis**:
- Small PR (< 1000 lines): ~$0.002-0.005
- Medium PR (1000-5000 lines): ~$0.01-0.02
- Large PR (> 5000 lines): ~$0.05-0.10

### 6.2 Cost Optimization

**Option 1: Analyze Only Recent PRs**
```yaml
ANALYSIS_DAYS: 1  # Only analyze PRs from last 24 hours
```

**Option 2: Reduce Diff Size**
Edit `ai-risk-analyzer.py` line 25:
```python
self.max_diff_size = 5000  # Reduced from 10000
```

**Option 3: Analyze on Demand**

Instead of triggering on every branch creation, trigger on schedule:

```yaml
on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM
```

**Option 4: Selective Analysis**

Analyze only certain files or repos:

```yaml
on:
  create:
    branches:
      - 'main'
      - 'release/**'
```

### 6.3 Cost Tracking

Monitor API usage at **https://console.anthropic.com → Usage**

The workflow prints estimated cost:
```
📊 AI API Usage Report
Model: Claude 3.5 Sonnet
Estimated cost: ~$0.01-0.05 per PR analyzed
```

---

## Part 7: Troubleshooting

### Problem: "API Error: 401 Unauthorized"

**Cause**: Invalid or missing Anthropic API key

**Solution**:
1. Verify `ANTHROPIC_API_KEY` secret exists in GitHub
2. Verify key is valid at https://console.anthropic.com
3. Regenerate key if needed

### Problem: "No module named anthropic"

**Cause**: Python dependencies not installed

**Solution**: Already handled in workflow. If running locally:
```bash
pip install anthropic
```

### Problem: "Timeout - API taking too long"

**Cause**: Large diffs or network issues

**Solution**:
1. Reduce `max_diff_size` in `ai-risk-analyzer.py`
2. Reduce `ANALYSIS_DAYS`
3. Increase timeout in workflow

### Problem: "API Rate Limited"

**Cause**: Too many API calls

**Solution**:
1. Reduce analysis frequency
2. Reduce number of PRs analyzed
3. Use smaller diff sizes

### Problem: "Report shows 'unknown' severity"

**Cause**: AI couldn't parse response or API error

**Solution**:
1. Check GitHub Actions logs for detailed error
2. Verify API key validity
3. Try again (might be transient issue)

---

## Part 8: Advanced Usage

### 8.1 Running Locally

Test AI analysis locally before deploying:

```bash
# Install dependencies
pip install anthropic requests

# Run analysis
python .github/scripts/ai-risk-analyzer.py \
  --repo "owner/repo" \
  --github-token "ghp_your_token" \
  --claude-token "sk-ant_your_key" \
  --days 7
```

### 8.2 Custom Risk Categories

Modify the prompt in `ai-risk-analyzer.py` to add custom analysis:

```python
**Analyze for:**
1. **Security Risks**: [default]
2. **Code Quality**: [default]
3. **Compliance**: [CUSTOM] Check for GDPR/HIPAA concerns
4. **Performance**: [CUSTOM] Database query optimization
5. **DevOps**: [CUSTOM] Infrastructure-as-code issues
```

### 8.3 Integration with Slack

Add to `.github/workflows/pr-risk-analysis-ai.yml`:

```yaml
      - name: Notify Slack on critical risks
        if: failure()
        uses: slackapi/slack-github-action@v1.24.0
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {
              "text": "🔴 Critical AI Risk Detected",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*PR Risk Alert*\nAI detected critical security/quality risks.\nCheck: ${{ github.server_url }}/${{ github.repository }}/actions"
                  }
                }
              ]
            }
```

**Setup**:
1. Create Slack webhook: https://api.slack.com/messaging/webhooks
2. Add to GitHub secrets as `SLACK_WEBHOOK`

### 8.4 Database Persistence

Store reports in your database:

```python
# After generating report
import sqlite3

conn = sqlite3.connect('pr_risks.db')
c = conn.cursor()
c.execute('''
  INSERT INTO pr_analyses 
  (timestamp, repo, critical_risks, ai_model)
  VALUES (?, ?, ?, ?)
''', (
  report['timestamp'],
  report['repository'],
  report['summary']['critical_risks'],
  report['ai_model']
))
conn.commit()
```

---

## Part 9: Performance & Best Practices

### 9.1 Optimize Analysis

- ✓ Limit to last 7 days for weekly checks
- ✓ Use reasonable diff size limits (10KB)
- ✓ Cache results when possible
- ✗ Don't analyze all historical PRs
- ✗ Don't use very large diff sizes (>50KB)

### 9.2 Team Communication

1. **Share reports** with engineering team weekly
2. **Discuss findings** in retrospectives
3. **Act on recommendations** from AI
4. **Adjust thresholds** based on team capabilities

### 9.3 Iterative Improvement

**Week 1**: Run analysis, observe patterns
**Week 2**: Adjust thresholds based on data
**Week 3**: Address top-risk categories
**Week 4**: Review trends, celebrate improvements

---

## Part 10: Comparison: Rule-Based vs AI

| Aspect | Rule-Based | AI-Powered |
|--------|-----------|-----------|
| Credential detection | ✓ Pattern matching | ✓✓ Context-aware |
| Security vulnerabilities | ✓ Known patterns | ✓✓ Novel patterns |
| Code quality | ✓ Metrics | ✓✓ Contextual |
| Design issues | ✗ Cannot detect | ✓✓ Can identify |
| False positives | Medium | Low |
| False negatives | High | Low |
| Cost | Free | ~$0.01-0.05/PR |
| Speed | Fast (~1s) | Slower (~10-30s) |

**Recommendation**: Use both:
- Rule-based for fast, free checks on every PR
- AI-powered for weekly deep analysis

---

## Part 11: Hybrid Approach

Run BOTH analyzers for best results:

```yaml
jobs:
  rule-based-analysis:
    # Fast, free check on every PR
    uses: ./.github/workflows/pr-risk-analysis.yml
  
  ai-powered-analysis:
    # Deep AI analysis on schedule
    if: github.event_name == 'schedule'
    uses: ./.github/workflows/pr-risk-analysis-ai.yml
```

This gives you:
- ✓ Instant feedback (rule-based)
- ✓ Deep insights (AI weekly)
- ✓ Optimized costs
- ✓ Best of both worlds

---

## Part 12: Feedback Loop

1. **Collect data** from AI analysis
2. **Identify patterns** (most common risks)
3. **Create guidelines** to prevent them
4. **Train team** on best practices
5. **Measure improvement** in subsequent analyses

Example:
- **Week 1**: AI finds 5 PRs with hardcoded secrets
- **Week 2**: Add pre-commit hooks for secret detection
- **Week 3**: Zero new hardcoded secrets detected
- ✅ Problem solved!

---

## Support

**Anthropic Documentation**: https://docs.anthropic.com  
**GitHub Actions Help**: https://docs.github.com/actions  
**API Status**: https://status.anthropic.com  

---

**Version**: 1.0  
**Last Updated**: January 2024  
**Compatible**: GitHub Actions, All languages, All .NET versions
