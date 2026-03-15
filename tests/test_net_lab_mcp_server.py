"""
EVE-NG MCP – Quick smoke test
==============================
Tests the internal helper functions of eveng_mcp_server.py directly
(bypasses MCP transport entirely — pure API validation).

Usage:
  export EVE_NG_HOST=192.168.100.10
  export EVE_NG_USERNAME=admin
  export EVE_NG_PASSWORD=eve
  export EVE_NG_PORT=80

  # Required: lab path and node name to exercise
  export EVE_NG_TEST_LAB=/MyLab.unl
  export EVE_NG_TEST_NODE=R1

  python test_eveng.py

The telnet step launches an interactive telnet session in your terminal.
Press Ctrl+] then 'quit' to exit telnet and return to the script.
"""

import asyncio
import os
import subprocess
import sys

# ── Import the server module (assumes same directory or on PYTHONPATH) ────────
sys.path.insert(0, os.path.dirname(__file__))
import net_lab_mcp_server as srv

# ── Test config from env ──────────────────────────────────────────────────────
LAB_PATH  = os.environ.get("EVE_NG_TEST_LAB",  "/test_lab.unl")
NODE_NAME = os.environ.get("EVE_NG_TEST_NODE", "VMX")
FOLDER    = os.environ.get("EVE_NG_TEST_FOLDER", "/")

# ── Helpers ───────────────────────────────────────────────────────────────────
def section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")

def ok(msg: str)   -> None: print(f"  ✓  {msg}")
def fail(msg: str) -> None: print(f"  ✗  {msg}"); sys.exit(1)

# ── Test steps ────────────────────────────────────────────────────────────────

async def test_auth() -> None:
    section("1 · Authentication")
    try:
        # _get_session() triggers the POST /auth/login internally
        await srv._get_session()
        # Confirm session is live with a lightweight call
        data = await srv._api("GET", "/status")
        version = data.get("data", {}).get("version", "unknown")
        ok(f"Authenticated — EVE-NG version: {version}")
    except Exception as e:
        fail(f"Auth failed: {e}")


async def test_list_labs() -> None:
    section("2 · List labs")
    try:
        result = await srv.eveng_list_labs(FOLDER)
        print(result)
        ok("Lab listing complete")
    except Exception as e:
        fail(f"List labs failed: {e}")


async def test_list_nodes_before_start() -> None:
    section(f"3 · List nodes in '{LAB_PATH}' (before start)")
    try:
        result = await srv.eveng_list_nodes(LAB_PATH)
        print(result)
        ok("Node listing complete")
    except Exception as e:
        fail(f"List nodes failed: {e}")


async def test_start_node() -> None:
    section(f"4 · Start node '{NODE_NAME}'")
    # Resolve node ID by name first
    data = await srv._api("GET", f"/labs{srv._encode_path(LAB_PATH)}/nodes")
    nodes = data.get("data", {})

    node_id = None
    for nid, node in nodes.items():
        if node.get("name", "").lower() == NODE_NAME.lower():
            node_id = nid
            break

    if not node_id:
        fail(f"Node '{NODE_NAME}' not found in '{LAB_PATH}' — check EVE_NG_TEST_NODE")

    try:
        result = await srv.eveng_start_nodes(LAB_PATH, node_id)
        print(f"  Response: {result}")
        ok(f"Start issued for node_id={node_id}")
    except Exception as e:
        fail(f"Start node failed: {e}")

    # Brief pause to let EVE-NG boot the node process
    print("  Waiting 5 s for node to initialise…")
    await asyncio.sleep(5)


async def test_list_nodes_after_start() -> None:
    section(f"5 · List nodes in '{LAB_PATH}' (after start)")
    try:
        result = await srv.eveng_list_nodes(LAB_PATH)
        print(result)
        ok("Node listing complete")
    except Exception as e:
        fail(f"List nodes failed: {e}")


async def test_telnet(host: str, port: int) -> None:
    """Launch an interactive telnet session in the foreground terminal."""
    section(f"6 · Telnet to {NODE_NAME}  →  {host}:{port}")
    print(f"  Launching: telnet {host} {port}")
    print("  Press  Ctrl+]  then type  quit  to exit telnet and return here.\n")
    subprocess.run(["telnet", host, str(port)])


async def resolve_console(skip_interactive: bool = False) -> tuple[str, int]:
    """Return (host, port) for NODE_NAME, optionally skipping interactive telnet."""
    section(f"6 · Resolve console URL for '{NODE_NAME}'")
    try:
        cmd = await srv.eveng_telnet_command(LAB_PATH, NODE_NAME)
        print(f"  Console command: {cmd}")
        ok("Console URL resolved")
    except Exception as e:
        fail(f"Console resolution failed: {e}")

    # Parse "telnet <host> <port>"
    parts = cmd.split()
    if len(parts) != 3 or parts[0] != "telnet":
        fail(f"Unexpected telnet command format: '{cmd}'")

    return parts[1], int(parts[2])


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\n╔══════════════════════════════════════════════════╗")
    print("║        EVE-NG MCP Server – Smoke Test            ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"  Host   : {srv._cfg('EVE_NG_HOST', '(not set)')}")
    print(f"  Lab    : {LAB_PATH}")
    print(f"  Node   : {NODE_NAME}")

    await test_auth()
    await test_list_labs()
    await test_list_nodes_before_start()
    await test_start_node()
    await test_list_nodes_after_start()

    host, port = await resolve_console()

    # Ask before launching interactive session
    print(f"\n  Ready to open telnet {host} {port}")
    answer = input("  Open interactive telnet session now? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        await test_telnet(host, port)
    else:
        print("  Skipping telnet — done.")

    section("All tests passed ✓")


if __name__ == "__main__":
    asyncio.run(main())