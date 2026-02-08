"""
Real-World Test: Network Device Troubleshooting with RLM
=========================================================

This script simulates gathering configs and operational status from 1000+ devices
and using RLM middleware to find issues without context overflow.

Usage:
    python test_network_scenario.py
"""

import json
import random
from typing import Dict, Any
from rlm_middleware_final import NetworkDeviceRLMMiddleware, RLMConfig
import sys 
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
import creds

# Import DeepAgents components
try:
    from deepagents import create_deep_agent
    from langchain_core.tools import tool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("⚠️  DeepAgents not installed. Install with: pip install deepagents langchain-openai")



def generate_realistic_device_data(num_devices: int = 1000) -> Dict[str, Any]:
    """
    Generate realistic network device data for testing.
    
    Simulates:
    - Mix of routers, switches, firewalls
    - Real-ish configurations
    - Operational status with some issues
    - Multiple sites/data centers
    """
    devices = {}
    
    # Device models and vendors
    models = [
        ('Cisco', 'ASR-9000', 'router'),
        ('Cisco', 'Catalyst-9300', 'switch'),
        ('Cisco', 'Nexus-9300', 'switch'),
        ('Arista', '7050SX', 'switch'),
        ('Arista', '7280R', 'switch'),
        ('Juniper', 'MX960', 'router'),
        ('Juniper', 'QFX5100', 'switch'),
        ('Palo Alto', 'PA-5220', 'firewall'),
    ]
    
    sites = ['DC1', 'DC2', 'DC3', 'Branch-West', 'Branch-East', 'HQ', 'DR-Site']
    
    # Simulate some common issues
    issue_patterns = {
        'bgp_flap': 0.05,  # 5% of devices
        'high_cpu': 0.08,  # 8% of devices
        'config_drift': 0.12,  # 12% of devices
        'version_mismatch': 0.15,  # 15% of devices
        'weak_snmp': 0.10,  # 10% of devices
    }
    
    for i in range(num_devices):
        vendor, model, dev_type = random.choice(models)
        site = random.choice(sites)
        
        device_id = f"{site}-{dev_type}-{i % 100:03d}"
        ip = f"10.{i // 256}.{(i % 256) // 16}.{i % 16}"
        
        # Determine if this device has issues
        has_bgp_issue = random.random() < issue_patterns['bgp_flap']
        has_cpu_issue = random.random() < issue_patterns['high_cpu']
        has_config_issue = random.random() < issue_patterns['config_drift']
        has_version_issue = random.random() < issue_patterns['version_mismatch']
        has_snmp_issue = random.random() < issue_patterns['weak_snmp']
        
        # Generate operational facts
        cpu = random.randint(85, 98) if has_cpu_issue else random.randint(15, 75)
        memory = random.randint(80, 95) if has_cpu_issue else random.randint(30, 70)
        
        facts = {
            'hostname': device_id,
            'ip': ip,
            'vendor': vendor,
            'model': model,
            'type': dev_type,
            'site': site,
            'os_version': f"{'15.1' if has_version_issue else '17.3'}.{random.randint(1, 9)}",
            'uptime_days': random.randint(1, 365),
            'cpu_5min': cpu,
            'memory_used_percent': memory,
            'interfaces': {
                f'GigabitEthernet0/{j}': {
                    'status': 'up' if random.random() > 0.1 else 'down',
                    'speed': '1000',
                    'errors': random.randint(0, 1000),
                }
                for j in range(random.randint(4, 24))
            }
        }
        
        # Add BGP for routers
        if dev_type == 'router':
            facts['bgp_neighbors'] = [
                {
                    'peer_ip': f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{j}",
                    'peer_as': 65000 + random.randint(0, 100),
                    'state': 'Idle' if (has_bgp_issue and j < 2) else 'Established',
                    'uptime': f"{random.randint(0, 30)}d{random.randint(0, 23)}h" if not has_bgp_issue else "0d0h",
                    'prefixes_received': random.randint(100, 50000) if not has_bgp_issue else 0,
                }
                for j in range(random.randint(2, 6))
            ]
        
        # Generate configuration
        config_lines = [
            f"hostname {device_id}",
            "!",
            f"! {vendor} {model}",
            "!",
        ]
        
        # SNMP config (some with weak communities)
        if has_snmp_issue:
            config_lines.extend([
                "snmp-server community public RO",
                "!",
            ])
        else:
            config_lines.extend([
                f"snmp-server community {random.choice(['SecureComm123', 'NetworkOps!', 'Monitoring2024'])} RO",
                "!",
            ])
        
        # NTP config (some missing)
        if random.random() > 0.2:
            config_lines.extend([
                "ntp server 10.0.0.100",
                "ntp server 10.0.0.101",
                "!",
            ])
        
        # Syslog (some missing)
        if random.random() > 0.3:
            config_lines.extend([
                "logging host 10.0.0.200",
                "logging buffered 50000",
                "!",
            ])
        
        # BGP config for routers
        if dev_type == 'router':
            config_lines.extend([
                f"router bgp 65{i % 100:03d}",
                " bgp log-neighbor-changes",
            ])
            
            # BGP auth (some missing - config drift issue)
            for neighbor in facts.get('bgp_neighbors', []):
                peer_ip = neighbor['peer_ip']
                if has_config_issue:
                    config_lines.append(f" neighbor {peer_ip} remote-as {neighbor['peer_as']}")
                else:
                    config_lines.extend([
                        f" neighbor {peer_ip} remote-as {neighbor['peer_as']}",
                        f" neighbor {peer_ip} password 7 encrypted_password_here",
                    ])
            config_lines.append("!")
        
        # Interfaces
        for intf_name in list(facts['interfaces'].keys())[:3]:  # Sample interfaces
            config_lines.extend([
                f"interface {intf_name}",
                " description Connected to network",
                " no shutdown",
                "!",
            ])
        
        config_lines.extend([
            "end",
            ""
        ])
        
        devices[device_id] = {
            'ip': ip,
            'facts': facts,
            'config': '\n'.join(config_lines),
        }
    
    return devices


def test_scenario_without_rlm():
    """
    Show what happens WITHOUT RLM - context overflow.
    """
    print("\n" + "="*80)
    print("TEST 1: Without RLM (Will Fail)")
    print("="*80)
    
    devices = generate_realistic_device_data(1000)
    
    # Calculate total size
    total_chars = len(json.dumps(devices))
    total_kb = total_chars / 1024
    total_mb = total_kb / 1024
    
    print(f"\nGenerated data for {len(devices)} devices:")
    print(f"  Total size: {total_chars:,} characters")
    print(f"  Size in KB: {total_kb:,.2f} KB")
    print(f"  Size in MB: {total_mb:,.2f} MB")
    print(f"\n❌ This exceeds typical LLM context windows (128K-200K tokens)")
    print(f"   Even with 200K token limit, this is ~{total_chars/4:,.0f} tokens (assuming 4 chars/token)")
    print(f"\n💡 Solution: Use RLM middleware to handle this data programmatically")


def test_scenario_with_rlm():
    """
    Show how RLM handles 1000+ devices gracefully.
    """
    if not LANGCHAIN_AVAILABLE:
        print("\n⚠️  DeepAgents not available. Please install to run this test.")
        return
    
    print("\n" + "="*80)
    print("TEST 2: With RLM Middleware (Success)")
    print("="*80)
    
    # Generate data
    print("\n📊 Generating realistic device data...")
    devices = generate_realistic_device_data(1000)
    
    total_chars = len(json.dumps(devices))
    print(f"✓ Generated {len(devices)} devices ({total_chars/1024/1024:.2f} MB)")
    
    # Setup RLM
    print("\n🔧 Setting up RLM middleware...")
    
    # Import model
    from langchain_openai import ChatOpenAI
    #main model
    main_model = ChatOpenAI(model="gpt-5-mini", temperature=0, api_key=creds.OPENAI_KEY)
    
    # Use sub-model for llm_query calls
    sub_model = ChatOpenAI(model="gpt-5-nano", temperature=0, api_key=creds.OPENAI_KEY)
    
    rlm_middleware = NetworkDeviceRLMMiddleware(
        model=sub_model,
        config=RLMConfig(
            max_iterations=50,
            large_output_threshold=30000,  # 30KB
        ),
        initial_context=devices  # Load all device data into RLM context
    )
    
    print("✓ RLM middleware configured")
    print(f"  - Context loaded: {len(devices)} devices")
    print(f"  - Tools available: {len(rlm_middleware.tools)}")
    print(f"  - Sub-LLM configured for semantic analysis")
    
    # Create tool for getting device count
    @tool
    def get_device_count() -> str:
        """Get the total number of devices being monitored."""
        return f"Total devices: {len(devices)}"
    
    # Create deep agent with RLM middleware
    print("\n🤖 Creating deep agent with RLM middleware...")
    
    # Combine RLM tools with custom tools
    all_tools = [get_device_count] + rlm_middleware.tools
    
    agent = create_deep_agent(
        model=main_model,  # Main agent model
        tools=all_tools,
        middleware=[rlm_middleware],  # Add RLM middleware
        system_prompt="""You are a network operations expert analyzing device data.
        
The device data is already loaded in the RLM 'context' variable.
Use RLM tools to analyze it efficiently:
- rlm_context_info: Check what data you have
- rlm_execute_code: Filter and process data with Python
- rlm_get_variable: Retrieve results from code execution

Remember: The full device data is in 'context' - use code to filter first!"""
    )
    
    print("✓ Deep agent created with RLM capabilities")
    
    # Test query
    print("\n" + "="*80)
    print("🔍 RUNNING ANALYSIS")
    print("="*80)
    
    query = """
    Analyze the network devices to identify the root cause of any issues:
    
    1. First, use rlm_context_info to see what data structure we're working with
    2. Use rlm_execute_code to find devices with:
       - BGP sessions in non-Established state
       - High CPU (>80%)
       - Configuration issues (weak SNMP, missing BGP auth)
    3. Look for patterns - are issues correlated by site, vendor, or version?
    4. Provide a root cause analysis with specific recommendations
    
    Remember: The full device data is in the 'context' variable. Use code to filter first!
    """
    
    print(f"\n📝 Query:\n{query}\n")
    
    try:
        # Invoke the deep agent
        result = agent.invoke({
            "messages": [{"role": "user", "content": query}]
        })
        
        print("\n" + "="*80)
        print("✅ ANALYSIS COMPLETE")
        print("="*80)
        
        # Get the final message
        final_message = result["messages"][-1]
        print(f"\n{final_message.content}")
        
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()


def test_data_generation_only():
    """
    Just generate and save data for manual testing.
    """
    print("\n" + "="*80)
    print("TEST 3: Data Generation Only")
    print("="*80)
    
    print("\n📊 Generating device data...")
    devices = generate_realistic_device_data(1500)
    
    # Save to file
    output_file = "test_network_devices_1500.json"
    with open(output_file, 'w') as f:
        json.dump(devices, f, indent=2)
    
    total_chars = len(json.dumps(devices))
    
    print(f"\n✓ Generated {len(devices)} devices")
    print(f"  Size: {total_chars/1024/1024:.2f} MB")
    print(f"  Saved to: {output_file}")
    
    # Statistics
    by_type = {}
    issues_count = 0
    
    for device_id, data in devices.items():
        dev_type = data['facts']['type']
        by_type[dev_type] = by_type.get(dev_type, 0) + 1
        
        # Count issues
        facts = data['facts']
        if facts.get('cpu_5min', 0) > 80:
            issues_count += 1
        if 'bgp_neighbors' in facts:
            if any(n['state'] != 'Established' for n in facts['bgp_neighbors']):
                issues_count += 1
        if 'snmp-server community public' in data['config']:
            issues_count += 1
    
    print(f"\n📈 Statistics:")
    print(f"  By type: {by_type}")
    print(f"  Devices with issues: ~{issues_count}")
    
    print(f"\n💡 Use this file with RLM middleware to test on your own!")


def main():
    """Run all tests."""
    print("="*80)
    print("RLM Middleware - Real-World Network Scenario Test")
    print("="*80)
    
    # Test 1: Show the problem
    test_scenario_without_rlm()
    
    # Test 2: Show the solution (requires API key)
    print("\n")
    response = input("Run full RLM test with LangChain? (requires OPENAI_API_KEY) [y/N]: ")
    if response.lower() == 'y':
        test_scenario_with_rlm()
    else:
        print("\nℹ️  Skipping full test. Set OPENAI_API_KEY and run with 'y' to see RLM in action.")
    
    # Test 3: Generate data for manual testing
    print("\n")
    response = input("Generate test data file for manual testing? [y/N]: ")
    if response.lower() == 'y':
        test_data_generation_only()


if __name__ == "__main__":
    main()