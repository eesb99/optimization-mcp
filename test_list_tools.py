#!/usr/bin/env python3
"""Test MCP list_tools"""

import asyncio
import json
import subprocess

async def test_list_tools():
    """Test list_tools request"""

    proc = await asyncio.create_subprocess_exec(
        "venv/bin/python", "server.py",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Initialize
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }
    proc.stdin.write((json.dumps(init_request) + "\n").encode())
    await proc.stdin.drain()
    await proc.stdout.readline()  # Read init response

    # Send initialized notification
    initialized = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
    proc.stdin.write((json.dumps(initialized) + "\n").encode())
    await proc.stdin.drain()

    # Request tools list
    list_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    proc.stdin.write((json.dumps(list_request) + "\n").encode())
    await proc.stdin.drain()

    # Read response
    try:
        response_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
        response = json.loads(response_bytes.decode())

        print("=== tools/list Response ===")
        if "result" in response:
            tools = response["result"].get("tools", [])
            print(f"\nTools found: {len(tools)}")
            for tool in tools:
                print(f"  - {tool['name']}")
        else:
            print(json.dumps(response, indent=2))

    except asyncio.TimeoutError:
        print("Timeout")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        proc.terminate()
        await proc.wait()

if __name__ == "__main__":
    asyncio.run(test_list_tools())
