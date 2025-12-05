# Troubleshooting Guide - Optimization MCP

**Issue**: MCP not connecting to Claude Desktop
**Last Updated**: 2025-12-05

---

## Root Cause Found

**ISSUE**: The `optimization-mcp` was NOT added to Claude Desktop configuration file.

**SOLUTION APPLIED**: Added configuration to `claude_desktop_config.json`

---

## Diagnostic Results

### 1. Server Status - OK
- Server starts successfully (tested standalone)
- All dependencies installed (mcp, pulp, scipy, numpy, cvxpy, networkx)
- Python 3.13.5 available at `/opt/homebrew/Caskroom/miniconda/base/bin/python3`
- No errors in server startup

### 2. Configuration - FIXED
- **File location**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Configuration added**:
```json
"optimization-mcp": {
  "command": "/opt/homebrew/Caskroom/miniconda/base/bin/python3",
  "args": [
    "/Users/thianseongyee/.claude/mcp-servers/optimization-mcp/server.py"
  ]
}
```
- JSON syntax validated: VALID

### 3. Logs - WORKING
- Server has been running successfully (logs show multiple startups)
- Location: `/tmp/optimization-mcp.log`
- Last startup: 2025-12-05 12:32:11
- No errors detected

---

## Next Steps - REQUIRED

### CRITICAL: Restart Claude Desktop

The configuration change requires a **FULL RESTART**:

1. **Close all Claude Desktop windows**
2. **Press Cmd+Q** to fully quit the application
3. **Wait 3-5 seconds**
4. **Reopen Claude Desktop**

**WARNING**: Simply closing the window does NOT load new MCP configurations!

### Verify Connection

After restart, check in a new conversation:

1. Look for "Search and tools" slider/button
2. You should see 9 new tools:
   - optimize_allocation
   - optimize_robust
   - optimize_portfolio
   - optimize_schedule
   - optimize_execute
   - optimize_network_flow
   - optimize_pareto
   - optimize_stochastic
   - optimize_column_gen

### Test a Tool

Try asking Claude:
```
"Optimize allocation of $100,000 across 3 marketing channels with these ROI values:
- Google Ads: $125,000 return for $25,000 spend
- LinkedIn: $87,000 return for $18,000 spend
- Facebook: $93,000 return for $22,000 spend"
```

---

## Common Issues

### Issue 1: Tools Still Not Appearing

**Check Claude Desktop logs:**
```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

Look for `mcp-server-optimization-mcp.log` with error messages.

**Common causes:**
- Did you use **Cmd+Q** to quit? (not just close window)
- Are paths absolute? (no `~` or relative paths)
- Is JSON valid? Test with `python3 -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json`

### Issue 2: Permission Denied

```bash
# Make server.py executable
chmod +x /Users/thianseongyee/.claude/mcp-servers/optimization-mcp/server.py
```

### Issue 3: Import Errors

```bash
# Verify dependencies
cd /Users/thianseongyee/.claude/mcp-servers/optimization-mcp
python3 -c "import mcp, pulp, scipy, numpy, cvxpy, networkx; print('OK')"

# Reinstall if needed
pip install -r requirements.txt
```

### Issue 4: Wrong Python Version

```bash
# Check Python version (need 3.10+)
python3 --version

# If using venv, don't use it for MCP - use system Python
which python3
```

### Issue 5: Server Crashes

**Check server log:**
```bash
tail -50 /tmp/optimization-mcp.log
```

**Test server directly:**
```bash
cd /Users/thianseongyee/.claude/mcp-servers/optimization-mcp
python3 server.py
# Should start without errors
# Press Ctrl+C to stop
```

---

## Quick Verification Script

Run this to verify everything:

```bash
#!/bin/bash
echo "=== Optimization MCP Diagnostic ==="

# 1. Check Python
echo "1. Python version:"
python3 --version

# 2. Check dependencies
echo -e "\n2. Dependencies:"
python3 -c "import mcp, pulp, scipy, numpy, cvxpy, networkx; print('   All OK')" 2>&1

# 3. Check config file
echo -e "\n3. Config file:"
if [ -f ~/Library/Application\ Support/Claude/claude_desktop_config.json ]; then
  echo "   EXISTS"
  python3 -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json > /dev/null && echo "   JSON VALID" || echo "   JSON INVALID"
  grep -q "optimization-mcp" ~/Library/Application\ Support/Claude/claude_desktop_config.json && echo "   optimization-mcp FOUND" || echo "   optimization-mcp NOT FOUND"
else
  echo "   NOT FOUND"
fi

# 4. Check server starts
echo -e "\n4. Server startup test:"
cd /Users/thianseongyee/.claude/mcp-servers/optimization-mcp
timeout 2 python3 server.py 2>&1 | head -3

echo -e "\n5. Log file:"
ls -lh /tmp/optimization-mcp.log 2>/dev/null || echo "   No log file yet"

echo -e "\n=== DONE ==="
echo "If all checks pass, restart Claude Desktop with Cmd+Q"
```

---

## Expected Behavior After Restart

### Successful Connection

You'll see in `~/Library/Logs/Claude/mcp-server-optimization-mcp.log`:
```
Starting Optimization MCP Server
Processing request of type ListToolsRequest
```

### In Claude Conversations

- 9 optimization tools available in tools list
- Can be called automatically when you ask optimization questions
- Works with monte-carlo-business MCP for integrated workflows

---

## Configuration Reference

**Your Current Setup:**
- **Python**: `/opt/homebrew/Caskroom/miniconda/base/bin/python3`
- **Server**: `/Users/thianseongyee/.claude/mcp-servers/optimization-mcp/server.py`
- **Config**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Logs**: `~/Library/Logs/Claude/mcp-server-optimization-mcp.log`

---

## Still Not Working?

1. **Verify config syntax:**
   ```bash
   python3 -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

2. **Check Claude Desktop version:**
   - Ensure you have Claude Desktop (not just web version)
   - Update to latest version if old

3. **Test server in isolation:**
   ```bash
   cd /Users/thianseongyee/.claude/mcp-servers/optimization-mcp
   python3 server.py
   # Should start and wait for input
   ```

4. **Check file permissions:**
   ```bash
   ls -la /Users/thianseongyee/.claude/mcp-servers/optimization-mcp/server.py
   # Should be executable: -rwx--x--x
   ```

---

**Fixed**: Configuration added to Claude Desktop
**Action Required**: Restart Claude Desktop with **Cmd+Q**
