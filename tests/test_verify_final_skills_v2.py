import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

import asyncio
from net_deepagent import create_network_agent
from deepagents.middleware.skills import SkillsMiddleware

async def verify():
    print("Creating network agent...")
    agent = await create_network_agent()
    
    # The agent is a LangGraph CompiledGraph.
    # We can't easily inspect the internal middleware from the compiled graph without diving into the nodes.
    # But we can try to look at the LAN_subagent definition passed to SubAgentMiddleware.
    
    # Let's try to find the subagent middleware in the graph nodes
    # The nodes are in agent.nodes
    # print(f"Agent nodes: {agent.nodes.keys()}")
    
    # Another way: inspect the graph's config or the middleware list if we can find it.
    # Actually, let's just run a tool call that triggers the LAN subagent and inspect the output.
    # Or better, let's mock the subagent call and see what prompt it receives.
    
    # Even simpler: Let's manually check if get_network_skills() returns the absolute paths
    from net_deepagent import get_network_skills
    skills = get_network_skills()
    print(f"Network skills discovered: {skills}")
    
    if not skills:
        print("FAILURE: No network skills discovered!")
        return

    # Check if they are absolute paths
    for s in skills:
        if not s.startswith("/"):
             print(f"FAILURE: Skill path is not absolute: {s}")
             return
        if not os.path.isdir(s):
             print(f"FAILURE: Skill path is not a directory: {s}")
             return
        if not os.path.exists(os.path.join(s, "SKILL.md")):
             print(f"FAILURE: SKILL.md missing in {s}")
             return

    print("SUCCESS: Network skills discovered and verified on disk.")
    
    # Now let's try to instantiate the SkillsMiddleware manually with FilesystemBackend and see if it lists them.
    from deepagents.backends import FilesystemBackend
    backend = FilesystemBackend()
    
    for skill_path in skills:
        print(f"\nTesting SkillsMiddleware with path: {skill_path}")
        # Note: SkillsMiddleware expects source_path. 
        # With my fix, source_path can be the skill directory itself.
        middleware = SkillsMiddleware(backend=backend, sources=[skill_path])
        
        # We need to call _list_skills or modify_request
        # _list_skills is internal but we can call it for verification
        from deepagents.middleware.skills import _list_skills
        metadata_list = _list_skills(backend, skill_path)
        
        if metadata_list:
            print(f"  Found skill: {metadata_list[0]['name']}")
            print(f"  Description: {metadata_list[0]['description'][:50]}...")
        else:
            print(f"  FAILURE: SkillsMiddleware failed to find skill in {skill_path}")
            return

    print("\nFINAL SUCCESS: SkillsMiddleware successfully parses skills using FilesystemBackend!")

if __name__ == "__main__":
    asyncio.run(verify())
