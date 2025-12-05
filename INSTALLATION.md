# Installation Guide - Optimization MCP for Claude

**Version**: 2.5.0
**Official Anthropic MCP Documentation**: https://modelcontextprotocol.io/quickstart

---

## Prerequisites

- **Python 3.10+** (tested with Python 3.13.5)
- **Claude Desktop** installed
- **Basic command line** familiarity

---

## Installation Steps

### 1. Install Dependencies

```bash
cd /path/to/optimization-mcp
pip install -r requirements.txt
```

**Required packages:**
- mcp >= 0.9.0
- pulp >= 2.7.0
- scipy >= 1.16.0
- numpy >= 2.3.0
- cvxpy >= 1.4.0
- networkx >= 3.0
- pytest >= 7.0.0 (for testing)

### 2. Verify Installation

```bash
# Test the server runs
python3 server.py

# Run tests (optional but recommended)
pytest tests/ -v
```

Expected: 51/51 tests passing

### 3. Configure Claude Desktop

**CRITICAL**: Use **absolute paths** (not relative paths or `~`)

#### Find Your Python Path

```bash
# macOS/Linux
which python3

# Example output: /opt/homebrew/Caskroom/miniconda/base/bin/python3
```

#### Edit Configuration File

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Create or edit the file:

```json
{
  "mcpServers": {
    "optimization-mcp": {
      "command": "/ABSOLUTE/PATH/TO/python3",
      "args": [
        "/ABSOLUTE/PATH/TO/optimization-mcp/server.py"
      ]
    }
  }
}
```

**Example (macOS):**

```json
{
  "mcpServers": {
    "optimization-mcp": {
      "command": "/opt/homebrew/Caskroom/miniconda/base/bin/python3",
      "args": [
        "/Users/yourusername/.claude/mcp-servers/optimization-mcp/server.py"
      ]
    }
  }
}
```

**Important Notes:**
- Replace `/ABSOLUTE/PATH/TO/python3` with your actual Python path
- Replace `/ABSOLUTE/PATH/TO/optimization-mcp` with your actual installation path
- On Windows, use double backslashes (`\\`) or forward slashes (`/`)
- Do NOT use `~` or relative paths

### 4. Restart Claude Desktop

**macOS**: Press **Cmd+Q** to fully quit, then reopen
**Windows**: Right-click system tray icon → Quit, then reopen

**WARNING**: Simply closing the window does NOT restart Claude properly!

### 5. Verify Tools Loaded

1. Open a new Claude conversation
2. Look for the "Search and tools" slider/button
3. You should see 9 optimization tools:
   - `optimize_allocation`
   - `optimize_robust`
   - `optimize_portfolio`
   - `optimize_schedule`
   - `optimize_execute`
   - `optimize_network_flow`
   - `optimize_pareto`
   - `optimize_stochastic`
   - `optimize_column_gen`

---

## Troubleshooting

### Tools Not Appearing

**Check Logs:**
```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp*.log

# Windows
%LOCALAPPDATA%\Claude\logs\mcp*.log
```

**Common Issues:**

1. **Relative paths used** → Use absolute paths in config
2. **Python not found** → Verify `which python3` path is correct
3. **Window closed, not quit** → Use Cmd+Q (macOS) or tray quit (Windows)
4. **Missing dependencies** → Run `pip install -r requirements.txt`
5. **Config syntax error** → Validate JSON at https://jsonlint.com/

### Verify Server Starts

```bash
python3 /ABSOLUTE/PATH/TO/server.py
```

Should start without errors. Press Ctrl+C to stop.

### Check Dependencies

```bash
python3 -c "import mcp, pulp, scipy, numpy, cvxpy, networkx; print('All dependencies OK')"
```

---

## MCP Naming & Conflicts

**Server Name**: `optimization-mcp`
**No Conflicts**: Verified unique among installed MCPs
**Integration**: Works with `monte-carlo-business` MCP (separate package)

This MCP does NOT conflict with:
- `monte-carlo-business` (complementary, provides input for optimization)
- Any other installed MCPs in `~/.claude/mcp-servers/`

---

## Distribution Options

### Option A: Manual Installation (Current)

1. Clone/download repository
2. Install dependencies
3. Add to `claude_desktop_config.json`
4. Restart Claude Desktop

### Option B: UV Package Manager (Recommended by Anthropic)

Install `uv`:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Config with uv:
```json
{
  "mcpServers": {
    "optimization-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/optimization-mcp",
        "run",
        "server.py"
      ]
    }
  }
}
```

### Option C: Python Package (Future)

Once published to PyPI:
```bash
pip install optimization-mcp
```

---

## Next Steps

After successful installation:

1. Read `README.md` for tool documentation
2. Check `docs/` folder for development notes
3. Try example from README.md:
   ```
   Ask Claude: "Optimize my marketing budget allocation across 3 channels"
   ```

---

## Support

**Issues**: Check logs at `~/Library/Logs/Claude/mcp*.log`
**Documentation**: https://modelcontextprotocol.io/
**This MCP**: See README.md for tool usage examples

---

**Version**: 2.5.0 (Production Ready - 9 Tools, 51/51 Tests Passing)
