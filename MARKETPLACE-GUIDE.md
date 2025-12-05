# Optimization MCP - Marketplace Distribution Guide

**Repository**: https://github.com/eesb99/optimization-mcp (PRIVATE)
**Version**: 2.5.0
**Author**: THIAN SEONG YEE <eesb99@gmail.com>
**Date**: 2025-12-05

---

## How Users Install Your Plugin

### Option 1: Add Your Repo as Marketplace (Recommended)

**Step 1: User adds your marketplace**
```bash
claude plugin marketplace add eesb99/optimization-mcp
```

**Step 2: User installs the plugin**
```bash
claude plugin install optimization-mcp
```

**Step 3: User runs setup (auto-triggered or manual)**
```bash
# If auto-setup doesn't run, user executes:
cd ~/.claude/plugins/optimization-mcp
./setup.sh
```

**Step 4: User reconnects Claude Code**
- Tools automatically available via MCP

---

### Option 2: Manual Installation (Current Method)

**Step 1: Clone repository**
```bash
git clone git@github.com:eesb99/optimization-mcp.git ~/.claude/mcp-servers/optimization-mcp
```

**Step 2: Run setup**
```bash
cd ~/.claude/mcp-servers/optimization-mcp
./setup.sh
```

**Step 3: Add to ~/.claude.json**
```json
{
  "mcpServers": {
    "optimization-mcp": {
      "command": "/Users/[username]/.claude/mcp-servers/optimization-mcp/run.sh"
    }
  }
}
```

**Step 4: Restart Claude Code**

---

## Publishing to Public Marketplaces

### To Smithery.ai (3,100+ plugins)

**Current Status**: Repository is PRIVATE - must make public first

**Steps to publish**:
1. Make repository public on GitHub
2. Visit smithery.ai developer portal
3. Submit integration with:
   - GitHub repo URL
   - Description (9 optimization tools)
   - Category: Productivity / Developer Tools
   - Keywords: optimization, linear-programming, operations-research

**Benefits**:
- Listed on smithery.ai marketplace
- Users can discover via browse/search
- Automatic updates when you push new versions

### To Official MCP Registry

**Registry URL**: https://registry.modelcontextprotocol.io

**Requirements** (based on research):
- Public GitHub repository
- Valid marketplace.json at `.claude-plugin/marketplace.json`
- Documentation (README.md)
- License file (MIT ✓)

**Submission Process**:
1. Make repository public
2. Submit to registry (via mcp-publisher CLI or web form)
3. Wait for review and approval
4. Listed in official registry

---

## Marketplace Configuration Files

### .claude-plugin/marketplace.json (✓ Created)

**Purpose**: Makes your repo a Claude Code marketplace
**Validation**: `claude plugin validate .claude-plugin/marketplace.json`
**Status**: ✓ Validation passed

**Key Features**:
- Defines optimization-mcp plugin
- MCP server configuration with ${CLAUDE_PLUGIN_ROOT}
- Metadata: description, keywords, category
- Auto-setup via run.sh script

### setup.sh (✓ Created)

**Purpose**: Auto-creates venv and installs dependencies
**Executable**: ✓ chmod +x applied
**Triggers**: On plugin installation or manual execution

### run.sh (✓ Created)

**Purpose**: Launches server.py with correct venv Python
**Executable**: ✓ chmod +x applied
**Auto-setup**: Calls setup.sh if venv missing

---

## Making Repository Public (Required for Marketplaces)

**Current Status**: PRIVATE repository

**To make public**:

1. **GitHub Web Interface**:
   - Go to https://github.com/eesb99/optimization-mcp
   - Settings → General → Danger Zone
   - "Change repository visibility" → Public
   - Confirm with repository name

2. **After making public, users can**:
   ```bash
   # Add your marketplace
   claude plugin marketplace add eesb99/optimization-mcp

   # Install your plugin
   claude plugin install optimization-mcp

   # It appears under:
   /plugin marketplace list  # Shows your marketplace
   /plugin install           # Shows available plugins
   ```

---

## What Users See

### In Marketplace List
```
❯ optimization-mcp-marketplace
  Source: GitHub (eesb99/optimization-mcp)
  Plugins: 1
```

### In Plugin Browser
```
optimization-mcp (v2.5.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Advanced optimization tools for Claude Code - 9 specialized
solvers for allocation, scheduling, portfolio, network flow,
Pareto analysis, stochastic programming, and column generation

Category: productivity
Author: THIAN SEONG YEE
License: MIT

Keywords: optimization, linear-programming, operations-research,
resource-allocation, scheduling, portfolio, network-flow, pareto,
stochastic, column-generation

MCP Servers: optimization-mcp
```

### After Installation
```bash
$ /mcp
Configured MCP Servers:
  ✔ optimization-mcp (connected, 9 tools)
```

---

## Current State

**Repository**: PRIVATE on GitHub
**Marketplace**: ✓ Created and validated
**Setup Scripts**: ✓ Created (setup.sh, run.sh)
**Ready to Publish**: YES - just need to make repo public

**Next Actions**:
1. Commit marketplace files to git
2. Push to GitHub
3. Make repository public (if desired)
4. Submit to Smithery.ai or share repo URL

**To keep private**: Users install manually via git clone (current method)
**To make public**: Anyone can add as marketplace and install via `/plugin install`

---

**Last Updated**: 2025-12-05
