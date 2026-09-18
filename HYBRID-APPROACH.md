# Hybrid Risk Analysis: Rule-Based + AI-Powered

## Executive Summary

Combine rule-based and AI-powered analysis for optimal cost, speed, and accuracy. Use rule-based checks for fast feedback on every PR, and AI analysis for weekly deep dives.

---

## Architecture Comparison

### Rule-Based Analysis (Original)

**Strengths:**
- ✓ Fast (1-2 seconds per analysis)
- ✓ Zero cost
- ✓ Runs on every PR
- ✓ Deterministic (same input = same output)
- ✓ Works with minimal context

**Weaknesses:**
- ✗ Pattern-based (misses novel attacks)
- ✗ High false positives
- ✗ Doesn't understand code context
- ✗ Can't detect logical flaws
- ✗ Missing architectural issues

**Best For:**
- Immediate feedback on every change
- Low-sensitivity screening
- Continuous monitoring
- Cost-free baseline

---

### AI-Powered Analysis (Claude)

**Strengths:**
- ✓ Understands code context deeply
- ✓ Detects novel vulnerabilities
- ✓ Low false positives
- ✓ Identifies design/architecture issues
- ✓ Provides actionable recommendations

**Weaknesses:**
- ✗ Slower (10-30 seconds per PR)
- ✗ Costs money ($0.01-0.05 per PR)
- ✗ Requires API token
- ✗ Rate limits apply
- ✗ Non-deterministic (AI reasoning varies)

**Best For:**
- Deep code reviews
- Security audits
- Weekly trend analysis
- High-value decisions

---

## Implementation: Hybrid Strategy

### Option 1: Rule-Based + Weekly AI (Recommended)

**Every PR (Rule-Based):**
- Fast checks run on every branch creation
- Catches obvious issues immediately
- No cost

**Weekly (AI-Powered):**
- Deep analysis of last 7 days of PRs
- Identifies subtle issues
- Provides insights for team improvement

**Setup:**

```yaml
# .github/workflows/pr-risk-analysis.yml - FAST, FREE
on:
  create:
    branches: ['**']
  # Runs on every branch creation

# .github/workflows/pr-risk-analysis-ai.yml - DEEP, WEEKLY
on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday
  # Runs weekly for deep analysis
```

**Cost**: ~$0-2/week (5-10 PRs × $0.01-0.05)

---

### Option 2: Tiered Analysis

**Tier 1 - All PRs (Rule-Based):**
- Sensitive file changes
- Insufficient reviews
- Test failures
- Large changesets

**Tier 2 - Pre-Release (Both):**
- Main branch PRs: Run AI analysis
- Higher confidence gate

**Tier 3 - On-Demand (AI):**
- Manual trigger via GitHub Actions
- Deep audit for specific PRs
- Security team reviews

**Setup:**

```yaml
# Rule-based on every PR
on:
  create:
    branches: ['**']

# AI on main branch PR merges
on:
  pull_request:
    branches: ['main']
    types: [closed]
    if: "merged == true"

# Manual AI on any PR
on:
  workflow_dispatch:
    inputs:
      pr_number:
        description: 'PR number to analyze'
```

**Cost**: ~$5-10/week (higher AI usage for main branch)

---

### Option 3: Risk-Based Escalation

**Low-Risk Changes** (Rule-Based Only):
- Documentation changes
- Version bumps
- Config updates

**Medium-Risk Changes** (Rule-Based + Email Alert):
- Feature changes
- New dependencies
- Infrastructure changes

**High-Risk Changes** (Both + AI + Slack Alert):
- Security features
- Authentication/authorization
- Cryptographic changes
- Data access changes

**Setup:**

```python
# In analyze-pr-risks.py
def categorize_change(files):
    if all(f in ['*.md', 'VERSION', 'config'] for f in files):
        return 'low'  # Rule-based only
    elif any(pattern in f for f in files for pattern in ['auth', 'crypto', 'secret']):
        return 'high'  # Both
    else:
        return 'medium'  # Rule-based + alert
```

**Cost**: ~$1-3/week (AI only for high-risk)

---

## Detailed Comparison Table

| Capability | Rule-Based | AI | Hybrid |
|-----------|-----------|-----|--------|
| **Sensitivity** | Medium | High | High |
| **Speed** | 1s | 20s | Both |
| **Cost** | $0 | $0.05/PR | $0.01-0.02/PR |
| **Credentials Detection** | Pattern | Context | Context + Pattern |
| **Vulnerability Detection** | Known CVEs | Novel patterns | Both |
| **Code Quality** | Metrics | Analysis | Deep |
| **Design Issues** | No | Yes | Yes |
| **False Positives** | High | Low | Low |
| **False Negatives** | High | Low | Low |
| **Latency** | <2s | 10-30s | Varies |
| **Scalability** | Unlimited | Rate-limited | Good |

---

## Decision Tree

Use this to choose when to run each analyzer:

```
PR Created
  │
  ├─ Sensitive Files Changed?
  │  ├─ Yes → Run Rule-Based + Immediate AI
  │  └─ No  → Run Rule-Based Only
  │
  ├─ Large Changeset (50+ files)?
  │  ├─ Yes → Run AI analysis
  │  └─ No  → Continue
  │
  ├─ Merging to Main?
  │  ├─ Yes → Run AI analysis
  │  └─ No  → Run Rule-Based only
  │
  └─ Weekly Schedule?
     ├─ Yes → Run AI on all recent PRs
     └─ No  → End
```

---

## Example Workflow

### Monday Morning (AI Deep Dive)

```yaml
name: Weekly AI Risk Analysis

on:
  schedule:
    - cron: '0 9 * * 1'  # Monday 9 AM

jobs:
  ai-analysis:
    runs-on: ubuntu-latest
    steps:
      # Run AI analysis on PRs from last 7 days
      # Generate report and share with team
      # Post to Slack
```

**Result**: Team sees weekly risk trends, patterns, and recommendations

### Every Branch Creation (Fast Rule-Based)

```yaml
name: Instant Risk Check

on:
  create:
    branches: ['**']

jobs:
  rule-based:
    runs-on: ubuntu-latest
    steps:
      # Run fast rule-based checks
      # Return immediate feedback
      # Flag obvious issues
```

**Result**: Developer gets instant feedback, no waiting

### Before Release (Both)

```yaml
name: Pre-Release Audit

on:
  pull_request:
    branches: ['release/**']

jobs:
  rule-based:
    runs-on: ubuntu-latest
    # ... fast checks
  
  ai-analysis:
    runs-on: ubuntu-latest
    # ... deep analysis
  
  manual-review:
    needs: [rule-based, ai-analysis]
    # ... security team review
```

**Result**: Release quality assurance before shipping

---

## Implementation Checklist

- [ ] **Phase 1: Rule-Based (Week 1)**
  - [ ] Set up rule-based analyzer
  - [ ] Get team feedback on thresholds
  - [ ] Adjust sensitivity

- [ ] **Phase 2: Add AI (Week 2)**
  - [ ] Get Anthropic API key
  - [ ] Set up AI analyzer
  - [ ] Test on sample PRs
  - [ ] Calculate costs

- [ ] **Phase 3: Hybrid Integration (Week 3)**
  - [ ] Schedule weekly AI runs
  - [ ] Set up notifications
  - [ ] Create reporting dashboard

- [ ] **Phase 4: Optimization (Week 4)**
  - [ ] Analyze cost vs value
  - [ ] Adjust frequency
  - [ ] Train team on using insights

- [ ] **Phase 5: Production (Week 5+)**
  - [ ] Monitor continuously
  - [ ] Iterate on rules
  - [ ] Share metrics with leadership

---

## Cost Breakdown Examples

### Small Team (5 developers, 10 PRs/week)

**Rule-Based Only:**
- Cost: $0
- Time: ~2s per PR
- Sensitivity: Medium

**Hybrid (Rule-Based + Weekly AI):**
- Cost: $0.50-1/week
- Time: 2s + 1 weekly report
- Sensitivity: High

**Recommendation**: Hybrid is worth the $1/week

---

### Large Team (50 developers, 100 PRs/week)

**Rule-Based Only:**
- Cost: $0
- Time: ~2s per PR
- Sensitivity: Medium

**Hybrid (Rule-Based + Weekly AI on last 7 days = ~15 PRs):**
- Cost: $0.15-0.75/week
- Time: 2s + 1 weekly report
- Sensitivity: High

**Tiered Approach (AI only for main branch = ~3 PRs/week):**
- Cost: $0.03-0.15/week
- Time: 2s + 20s for main PRs
- Sensitivity: Very High

**Recommendation**: Tiered approach is most cost-effective

---

## Monitoring & Metrics

### Weekly Report Metrics

```python
# Track for continuous improvement
metrics = {
    'rule_based_findings': 5,      # Issues caught by rules
    'ai_findings': 3,               # Issues caught only by AI
    'critical_risks': 1,            # High-severity issues
    'false_positives': 0.5,         # False alarm rate %
    'developer_satisfaction': 4.2,  # Out of 5
    'cost_per_pr': 0.02,            # Average cost
    'time_to_fix': 2.3              # Days from detection to fix
}
```

### When to Adjust Strategy

- **High false positive rate** → Relax rule-based thresholds
- **Missed vulnerabilities** → Increase AI analysis frequency
- **High costs** → Switch to tiered approach
- **Slow feedback** → Reduce diff sizes in AI analysis
- **Team frustration** → Reduce alert frequency

---

## Team Communication

### Monthly Status Report

```
🎯 PR Risk Analysis Report - January 2024

Rule-Based Analysis (Every PR):
  ✓ 240 PRs analyzed
  ✓ 12 critical issues caught
  ✓ 0 false positives

AI-Powered Analysis (Weekly):
  ✓ 52 PRs deep-analyzed
  ✓ 8 additional issues identified
  ✓ Top risk category: [Security] Credential exposure
  
Trends:
  📈 Authentication/Authorization: +2 issues
  📉 Code Quality: -1 issue
  → Team action: Add auth best practices workshop

Cost Analysis:
  Total Cost: $12.50
  Cost per PR analyzed: $0.015
  ROI: 1 vulnerability found per $1.56 spent
  Status: ✅ Within budget
```

---

## Production Readiness Checklist

Before going live with hybrid approach:

- [ ] Both analyzers tested and working
- [ ] API keys secured in GitHub secrets
- [ ] Alerts configured (Slack, email, etc.)
- [ ] Team trained on interpreting results
- [ ] SLAs defined for remediation
- [ ] Cost tracking enabled
- [ ] Escalation procedures documented
- [ ] Regular review schedule established
- [ ] Dashboard created for visibility
- [ ] Success metrics defined

---

## Continuous Improvement Loop

```
Deploy Hybrid
    ↓
Week 1: Collect Data
    ├─ Rule-based findings
    ├─ AI-powered findings
    ├─ Developer feedback
    └─ False positive rate
    ↓
Week 2: Analyze Patterns
    ├─ Most common risks
    ├─ Missed vulnerabilities
    ├─ False alarms
    └─ Cost efficiency
    ↓
Week 3: Make Adjustments
    ├─ Tune thresholds
    ├─ Change frequency
    ├─ Add team guidelines
    └─ Update training
    ↓
Week 4: Measure Impact
    ├─ Improvement metrics
    ├─ Cost/benefit analysis
    ├─ Team satisfaction
    └─ Security metrics
    ↓
Loop → Back to Collect Data
```

---

## Conclusion

The hybrid approach gives you:

✅ **Fast feedback** from rule-based analysis (every PR)  
✅ **Deep insights** from AI analysis (weekly)  
✅ **Reasonable costs** (~$1-5 per week)  
✅ **High accuracy** (low false positives/negatives)  
✅ **Scalability** (works for teams of any size)  
✅ **Team buy-in** (fast feedback + actionable insights)  

**Recommended Implementation**:
1. Start with rule-based (baseline)
2. Add weekly AI (insights)
3. Monitor and optimize (continuous improvement)
4. Scale as needed (tiered for large teams)

---

**Version**: 1.0  
**Created**: January 2024  
**Updated**: January 2024
