#!/usr/bin/env python
"""
Quick diagnostic script to test A2A agent discovery.
Run this to see if agents are being registered correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

async def test_a2a_discovery():
    print("=" * 70)
    print("A2A Agent Discovery Test")
    print("=" * 70)
    
    # Import after path is set
    from services.agent_service import AgentService
    
    print("\n1. Creating AgentService...")
    service = AgentService()
    print(f"   ✅ Service created: {service is not None}")
    
    print("\n2. Initializing agent...")
    try:
        await service.initialize()
        print("   ✅ Agent initialized successfully")
    except Exception as e:
        print(f"   ❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n3. Checking A2A middleware...")
    print(f"   Middleware instance: {service.a2a_middleware}")
    print(f"   Remote agents: {list(service.a2a_middleware.remote_agents.keys())}")
    print(f"   A2A tools: {len(service.a2a_tools)}")
    
    print("\n4. Getting A2A agents...")
    agents = await service.get_a2a_agents()
    print(f"   Found {len(agents)} agents")
    
    if agents:
        print("\n5. Agent Details:")
        for name, info in agents.items():
            status = "🟢 ONLINE" if info['online'] else "🔴 OFFLINE"
            print(f"\n   {status} {name}")
            print(f"      URL: {info['url']}")
            if info['online']:
                print(f"      Description: {info.get('description', 'N/A')}")
                print(f"      Capabilities: {', '.join(info.get('capabilities', []))}")
    else:
        print("\n   ⚠️ No agents found!")
        print("   Check:")
        print("   - Registry file exists at a2a_capability/agents_registry.json")
        print("   - Registry file is valid JSON")
        print("   - Check logs above for errors")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(test_a2a_discovery())
