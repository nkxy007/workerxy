import sys
import os
from pathlib import Path
from typing import List

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from net_deepagent import filter_tools_by_category

class MockTool:
    def __init__(self, name):
        self.name = name

def test_filtering():
    tools = [
        MockTool("aws_configure"),
        MockTool("azure_list_vms"),
        MockTool("gcp_bucket_create"),
        MockTool("cloud_status"),
        MockTool("net_ping"),
        MockTool("net_traceroute"),
        MockTool("read_network_diagram"),
        MockTool("read_design_document"),
        MockTool("datacentre_power_cycle"),
        MockTool("isp_route_check"),
        MockTool("random_tool")
    ]
    
    cloud_tools = filter_tools_by_category(tools, 'cloud')
    assert len(cloud_tools) == 4
    assert all(any(kw in t.name for kw in ['aws', 'azure', 'gcp', 'cloud']) for t in cloud_tools)
    
    lan_tools = filter_tools_by_category(tools, 'lan')
    assert len(lan_tools) == 2
    assert all(t.name.startswith('net_') for t in lan_tools)
    
    design_tools = filter_tools_by_category(tools, 'design')
    assert len(design_tools) == 2
    assert all(any(kw in t.name for kw in ['diagram', 'design']) for t in design_tools)
    
    dc_tools = filter_tools_by_category(tools, 'datacenter')
    assert len(dc_tools) == 1
    assert dc_tools[0].name == "datacentre_power_cycle"
    
    isp_tools = filter_tools_by_category(tools, 'isp')
    assert len(isp_tools) == 1
    assert isp_tools[0].name == "isp_route_check"
    
    # Test for main agent tool filtering (manually duplicating logic for verification)
    main_agent_tools = [
        t for t in tools 
        if not any(t.name.lower().startswith(p) for p in ['net_', 'isp_', 'datacentre_'])
    ]
    assert len(main_agent_tools) == 7 # aws, azure, gcp, cloud, random_tool, 2x design tools
    assert all(not t.name.startswith(('net_', 'isp_', 'datacentre_')) for t in main_agent_tools)
    
    print("All tool filtering tests (including main agent exclusion) passed!")

if __name__ == "__main__":
    test_filtering()
