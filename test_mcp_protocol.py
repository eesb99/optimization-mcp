#!/usr/bin/env python3
"""Test MCP protocol initialization"""

import asyncio
import json
import subprocess
import sys

async def test_mcp():
    """Test MCP server protocol"""

    # Start server
    proc = await asyncio.create_subprocess_exec(
        "venv/bin/python", "server.py",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Send initialize request
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }

    request_str = json.dumps(init_request) + "\n"
    proc.stdin.write(request_str.encode())
    await proc.stdin.drain()

    # Read response
    try:
        response_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
        response = json.loads(response_bytes.decode())

        print("=== Server Response ===")
        print(json.dumps(response, indent=2))

        if "result" in response:
            caps = response["result"].get("capabilities", {})
            print("\n=== Capabilities ===")
            print(json.dumps(caps, indent=2))

            if caps.get("tools"):
                print("\n✓ Server declares tools capability")
            else:
                print("\n✗ Server does NOT declare tools capability")

    except asyncio.TimeoutError:
        print("Timeout waiting for response")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        proc.terminate()
        await proc.wait()

if __name__ == "__main__":
    asyncio.run(test_mcp())
