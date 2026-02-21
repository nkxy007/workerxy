import asyncio
import sys
import os

# Add the current directory to path so we can import mcp_servers
sys.path.append(os.getcwd())

from mcp_servers import execute_shell_command

async def test():
    print("Testing execute_shell_command with 'netstat -rn'...")
    output = await execute_shell_command("netstat -rn", "testing netstat")
    print("\nOutput from netstat:")
    print("-" * 20)
    print(output)
    print("-" * 20)
    
    # We could also test 'dig' or 'nc' if needed
    print("\nTesting execute_shell_command with 'dig google.com'...")
    output_dig = await execute_shell_command("dig google.com +short", "testing dig")
    print("\nOutput from dig:")
    print("-" * 20)
    print(output_dig)
    print("-" * 20)

if __name__ == "__main__":
    asyncio.run(test())
