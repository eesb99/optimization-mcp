# Optimization MCP Test Examples

## Test 1: Simple Marketing Budget Allocation

**Problem**: Allocate $100K across 3 marketing channels to maximize ROI

**Prompt to Claude**:
```
Use optimize_allocation to solve this:

I have $100,000 marketing budget to allocate across:
- Google Ads: Costs $25,000, Expected return $50,000
- LinkedIn: Costs $18,000, Expected return $35,000
- Content Marketing: Costs $32,000, Expected return $45,000

Find the optimal allocation to maximize total return.
```

**Expected Output**:
- Status: optimal
- Objective Value: ~130,000
- Allocation: Google Ads=1, LinkedIn=1, Content=1 (all selected)
- Resource Usage: $75K used, $25K remaining

---

## Test 2: Resource Constraint Problem

**Problem**: Multiple resources (budget AND time)

**Prompt**:
```
Use optimize_allocation:

Budget: $100,000
Time available: 200 hours

Projects:
- Project A: $30K, 50 hours, returns $100K
- Project B: $25K, 80 hours, returns $80K
- Project C: $40K, 60 hours, returns $90K
- Project D: $35K, 70 hours, returns $95K

Maximize return under both budget and time constraints.
```

**Expected Output**:
- Should select best combination that fits both constraints
- Shows utilization for BOTH budget and time
- Shadow prices for each resource

---

## Test 3: Infeasible Problem (should handle gracefully)

**Prompt**:
```
Use optimize_allocation:

Budget: $50,000

Projects:
- Project A: Costs $60,000, Returns $100,000

Maximize return.
```

**Expected Output**:
- Status: optimal
- Objective: 0 (selects nothing since Project A doesn't fit)
- Helpful message explaining no items fit within budget

---

## Test 4: Monte Carlo Integration

**Prompt**:
```
First, create a mock Monte Carlo output with these values:
- google_ads_return: P50 = $48,000
- linkedin_return: P50 = $33,000

Then use optimize_allocation with monte_carlo_integration mode="percentile", percentile="p50"
```

**Expected Output**:
- Uses P50 values from mock MC data
- Returns monte_carlo_compatible output
- Suggests next tool: validate_reasoning_confidence

---

## Quick Validation Command

Run this in your terminal:
```bash
cd ~/.claude/mcp-servers/optimization-mcp
source venv/bin/activate
python tests/test_allocation.py
```

Should show:
```
============================================================
All tests passed!
============================================================
```
