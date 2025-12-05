# How Users Install optimization-mcp

**Repository**: https://github.com/eesb99/optimization-mcp
**Status**: PUBLIC ✓
**Date**: 2025-12-05

---

## Installation via `/plugin` Command

### Step 1: Add Marketplace

Users add your repository as a plugin marketplace source:

```bash
claude plugin marketplace add eesb99/optimization-mcp
```

**What happens**:
- Claude Code downloads `.claude-plugin/marketplace.json` from your repo
- Registers "optimization-mcp-marketplace" as available source
- Plugin appears in browse list

### Step 2: Install Plugin

```bash
claude plugin install optimization-mcp
```

**What happens**:
1. Downloads repository to `~/.claude/plugins/optimization-mcp`
2. Runs `setup.sh` (creates venv, installs requirements.txt)
3. Configures MCP server using `run.sh` launcher
4. Adds to active MCP list

### Step 3: Verify

```bash
# Check MCP status
/mcp
```

**Expected output**:
```
Configured MCP Servers:
  ✔ optimization-mcp (connected, 9 tools)
```

### Step 4: Use Tools

In any Claude Code conversation:
```
"Help me optimize resource allocation for my marketing budget using
the optimization-mcp tools"
```

**Available tools**:
- optimize_allocation
- optimize_robust
- optimize_portfolio
- optimize_schedule
- optimize_execute
- optimize_network_flow
- optimize_pareto
- optimize_stochastic
- optimize_column_gen

---

## Verification Commands

### For Users to Check Installation

```bash
# List configured marketplaces
claude plugin marketplace list
# Should show: ❯ optimization-mcp-marketplace

# Check installed plugins
ls -d ~/.claude/plugins/*/
# Should show: ~/.claude/plugins/optimization-mcp/

# Verify venv created
ls ~/.claude/plugins/optimization-mcp/venv/bin/python
# Should exist after setup.sh runs

# Test MCP connection
/mcp
# Should show connected with 9 tools
```

---

## Troubleshooting

### If Plugin Doesn't Appear

**Check marketplace was added**:
```bash
claude plugin marketplace list | grep optimization
```

**Manually update marketplace**:
```bash
claude plugin marketplace update
```

### If Installation Fails

**Check setup.sh ran**:
```bash
ls ~/.claude/plugins/optimization-mcp/venv
# Should exist
```

**Run setup manually**:
```bash
cd ~/.claude/plugins/optimization-mcp
./setup.sh
```

### If MCP Shows "Capabilities: none"

**See**: `~/.claude/docs/troubleshooting.md` section "MCP Shows 'Capabilities: none'"

**Quick test**:
```bash
cd ~/.claude/plugins/optimization-mcp
python test_list_tools.py
# Should show: ✓ Tools found: 9
```

---

## What Users Get

**9 Production Tools**:
1. Resource allocation (LP/MILP)
2. Robust optimization (scenario-based)
3. Portfolio optimization (Sharpe ratio)
4. Project scheduling (dependencies)
5. Custom optimization (auto-solver)
6. Network flow (10-100x faster logistics)
7. Pareto frontier (multi-objective)
8. Stochastic programming (2-stage)
9. Column generation (large-scale)

**51 Unit Tests**: All passing
**4 Solvers**: PuLP, CVXPY, SciPy, NetworkX
**Documentation**: Complete with examples
**License**: MIT (open source)

---

## Example User Session

```bash
$ claude plugin marketplace add eesb99/optimization-mcp
✓ Added marketplace: optimization-mcp-marketplace

$ claude plugin install optimization-mcp
Downloading eesb99/optimization-mcp...
Running setup.sh...
Creating virtual environment...
Installing dependencies...
✓ Plugin installed successfully

$ claude
> /mcp
Configured MCP Servers:
  ✔ optimization-mcp (connected, 9 tools)

> Help me optimize my marketing budget allocation across 5 channels
  with a $100K total budget and minimum spend constraints

[Claude Code uses optimize_allocation tool]

> Now show me the Pareto frontier for profit vs sustainability

[Claude Code uses optimize_pareto tool]
```

---

**Installation URL**: `claude plugin marketplace add eesb99/optimization-mcp`
**Repository**: https://github.com/eesb99/optimization-mcp (PUBLIC)
**Last Updated**: 2025-12-05
