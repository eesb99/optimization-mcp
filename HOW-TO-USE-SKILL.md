# How to Trigger & Use the robust-optimization Skill

**Skill**: robust-optimization (v1.0.0)
**Location**: `~/.claude/skills/robust-optimization.md`
**Status**: ✅ Ready to use

---

## How to Trigger the Skill (3 Methods)

### Method 1: Slash Command (Direct)
```
/robust-optimization
```

**What happens**: Skill loads immediately, starts Phase 0

**Use when**: You know you want the full robust optimization workflow

---

### Method 2: Trigger Keywords (Natural)

Say any phrase containing these keywords:
- "**robust allocation**"
- "**uncertainty optimization**"
- "**robust decision**"
- "**optimize under uncertainty**"

**Examples that trigger**:
```
✅ "I need robust allocation for my marketing budget"
✅ "Find a robust decision under uncertainty"
✅ "Help me optimize under uncertainty"
✅ "I need uncertainty optimization for this project"
```

**What happens**: Claude detects keywords, loads skill automatically

**Use when**: Natural conversation, let Claude auto-detect intent

---

### Method 3: Skill Tool (Programmatic)
```python
Skill("robust-optimization")
```

**What happens**: Direct skill invocation

**Use when**: Automated workflows, scripting

---

## What Happens When Triggered

### The 7-Phase Automated Workflow

**Phase 0: Problem Classification** (~1 second)
- Claude analyzes your request
- Detects: allocation, portfolio, or scheduling problem
- You see: "Detected: Allocation problem"

**Phase 1: Problem Definition** (~1 minute, interactive)
- Claude asks questions via UI
- You provide: items, resources, objectives, uncertainty
- You see: Question dialogs, select answers
- Claude builds: problem_spec dict

**Phase 2: Monte Carlo Scenarios** (~30-60 seconds)
- Claude generates 10,000 uncertainty scenarios
- You see: "Generated 10K scenarios. P10=$180K, P50=$250K, P90=$320K"

**Phase 3: Base Optimization** (~5 seconds)
- Claude optimizes using P50 (median) values
- You see: "Base allocation: SEO 40%, Content 30%, Expected: $250K"

**Phase 4: Robust Optimization** (~10-30 seconds)
- Claude finds allocation working across scenarios
- You see: "Robust allocation: SEO 35%, Content 35%, Works in 92%"

**Phase 5: Confidence Validation** (~30-60 seconds)
- Claude calculates success probability
- You see: "87% confidence, key risks identified"

**Phase 6: Stress Testing** (~20-40 seconds)
- Claude identifies breaking points
- You see: "Breaks if SEO conversion < 2%"

**Phase 7: Report & Save** (~10 seconds)
- Claude generates comprehensive markdown report
- Saves to: `~/Claude/projects/optimization-reports/YYYY-MM-DD_HHMM_report.md`
- Updates memory
- You see: Full report location

**Total Time**: 2-5 minutes
**Your Effort**: Answer questions (~1 minute)
**Automation**: Claude handles 6 phases automatically

---

## What You Get

### Outputs

**1. Comprehensive Decision Report** (Markdown)
- Saved to: `~/Claude/projects/optimization-reports/`
- Includes:
  - Recommended allocation (robust)
  - Confidence level (87%)
  - Expected outcome ($240K)
  - Comparison: base vs robust
  - Breaking points ("Breaks if X < Y")
  - Risk analysis
  - Next steps

**2. Memory Entry** (Persistent)
- Saved to: `~/Claude/memory/decisions.json`
- Key: `robust-optimization-{timestamp}`
- Contains: Summary of decision and pattern

**3. Interactive Summary** (Chat)
- Claude presents key findings
- Shows: Allocation, confidence, risks
- Recommends: Actions to take

---

## Example Usage

### Example 1: Marketing Budget

**You say**:
```
"I need to allocate $100K marketing budget across SEO, Content, Paid Ads,
Email, and Events. Conversion rates are uncertain - I need a robust
allocation that works even if performance is worse than expected."
```

**Trigger**: "robust allocation" + "uncertain" detected ✓

**Claude does**:
1. Asks: Channel costs, expected ROI ± uncertainty, constraints
2. Generates 10K scenarios
3. Finds base allocation (P50)
4. Finds robust allocation (85%+ scenarios)
5. Validates confidence (87%)
6. Stress tests (identifies breaking points)
7. Generates report

**You get**:
- Robust allocation: SEO 35%, Content 35%, Paid 20%, Email 10%, Events 0%
- Confidence: 87% success
- Risk: Breaks if SEO conversion < 2%
- Report saved
- Time: ~4 minutes

---

### Example 2: Investment Portfolio

**You say**:
```
"I have $500K to invest. I need robust portfolio allocation that works
across different market conditions."
```

**Trigger**: "robust...allocation" detected ✓

**Claude does**:
1. Detects: Portfolio problem (mentions "invest", "portfolio")
2. Asks: Assets, expected returns, risk tolerance, correlations
3. Runs portfolio optimization workflow
4. Generates Sharpe ratio optimization
5. Tests across market scenarios
6. Reports robust allocation

**You get**:
- Robust weights: 50% US, 25% Intl, 15% Bonds, 10% Gold
- Sharpe: 0.48 (conservative)
- Works in: 88% of market scenarios
- Report with risk analysis

---

## Tool Calls Behind the Scenes

When skill executes, Claude automatically calls:

**Optimization MCP** (3-4 calls):
- `optimize_allocation` or `optimize_portfolio` or `optimize_schedule`
- `optimize_robust`
- (Plus MC-compatible output processing)

**Monte Carlo MCP** (3 calls):
- `run_business_scenario` (10K scenarios)
- `validate_reasoning_confidence` (success probability)
- `test_assumption_robustness` (breaking points)

**Claude Tools** (3-4 calls):
- `AskUserQuestion` (1-3 questions)
- `Write` (save report)
- `SlashCommand` (/remember for memory)
- `TodoWrite` (optional, track progress)

**Total**: ~10 tool calls, all automated

---

## Requirements

### Must Have
- ✅ optimization-mcp loaded (5 tools)
- ✅ monte-carlo-business MCP loaded (3 tools)

### Must Provide
- Problem description (what you're optimizing)
- Uncertainty estimates (mean ± std for parameters)
- Constraints (optional)

### Optional
- Multi-objective weights (if balancing goals)
- Risk tolerance (default: 0.85 = 85%)
- Time horizon (for scheduling)

---

## When to Use This Skill

**Use the skill when**:
- ✅ High uncertainty in assumptions
- ✅ High-stakes decision ($50K+)
- ✅ Need comprehensive analysis
- ✅ Want automated workflow
- ✅ Need professional report for stakeholders

**Don't use the skill when**:
- ❌ Low uncertainty (use tools directly)
- ❌ Simple allocation (just call optimize_allocation)
- ❌ Quick analysis (skill is comprehensive, takes 2-5 min)
- ❌ Don't have Monte Carlo MCP

---

## Quick Start Guide

### Step 1: Trigger
Say: "I need robust allocation for [your problem] under uncertainty"

### Step 2: Answer Questions
Claude asks 1-3 questions, you provide:
- Items/options to consider
- Resources/constraints
- Uncertainty ranges (mean ± std)

### Step 3: Wait (~3-4 minutes)
Claude automatically:
- Generates 10K scenarios
- Optimizes (base + robust)
- Validates confidence
- Stress tests
- Generates report

### Step 4: Review Report
Claude shows:
- Recommended allocation
- Confidence level
- Breaking points
- Full report location

### Step 5: Decide
Use the robust allocation with confidence!

---

## Comparison: Skill vs Direct Tool Use

| Aspect | Direct Tools | robust-optimization Skill |
|--------|-------------|---------------------------|
| **How to use** | Call each tool manually | Say trigger keywords or /command |
| **Steps** | 6-8 manual steps | 1 trigger + answer questions |
| **Time** | 10-20 minutes | 2-5 minutes |
| **Expertise** | Must know workflow | No expertise needed |
| **Output** | Individual results | Comprehensive report |
| **MC Integration** | Manual chaining | Automatic |
| **Report** | You format | Auto-generated |
| **Memory** | You save | Auto-saved |

**Recommendation**: Use skill for comprehensive analysis, use tools directly for quick one-off optimizations.

---

## Troubleshooting

### Skill Doesn't Trigger

**Issue**: You said keywords but skill didn't trigger

**Solutions**:
- Use explicit: `/robust-optimization`
- Check keywords: Must say "robust" + "allocation" or other triggers
- Try: "I need robust optimization under uncertainty" (multiple keywords)

### Skill Starts But Errors

**Issue**: Skill starts but fails during execution

**Check**:
- Is Monte Carlo MCP loaded? (`/mcp` to verify)
- Do you have both optimization-mcp and monte-carlo-business?
- Are all tools working? (test individually first)

### Questions Unclear

**Issue**: Phase 1 questions are confusing

**Solutions**:
- Answer with best estimates
- Can skip optional questions
- Claude adapts to your answers

---

## Summary

**How to trigger**: Say "robust allocation" + "uncertain" OR use `/robust-optimization`

**What happens**: Claude reads 803-line instruction file, executes 7 phases automatically

**How long**: 2-5 minutes total

**What you do**: Answer questions (~1 minute)

**What you get**: Comprehensive report with robust allocation + confidence + risks

**Value**: 4-8x faster than manual + professional quality output

---

**Ready to use! Just say: "I need robust allocation under uncertainty"** 🚀
