"""
Complete Working Example: RLM for Network Device Analysis

This example demonstrates analyzing a large network (200 devices)
with various issues using the RLM middleware within a Deep Agent.
"""

from rlm_middleware import RLMMiddleware, RLMConfig
import json

# Placeholder for create_deep_agent if not installed
try:
    from deepagents import create_deep_agent
except ImportError:
    create_deep_agent = None


def generate_sample_network_data(num_devices=200):
    """Generate realistic sample network device data."""
    device_facts = {}
    
    for i in range(num_devices):
        device_ip = f"10.{i // 256}.{(i // 16) % 16}.{i % 16}"
        
        # Device types and locations
        device_type = ['router', 'switch', 'firewall'][i % 3]
        location = ['DC1', 'DC2', 'DC3', 'Branch'][i % 4]
        vendor = ['Cisco', 'Arista', 'Juniper'][i % 3]
        
        # Basic facts
        device_facts[device_ip] = {
            'hostname': f'{device_type}-{location.lower()}-{i % 10}',
            'ip': device_ip,
            'type': device_type,
            'vendor': vendor,
            'location': location,
            'model': f'{vendor} Model-{1000 + i % 100}',
            'version': f'{15 + i % 3}.{i % 10}.{i % 5}',
            
            # Performance metrics
            'cpu_percent': (i * 13) % 100,
            'memory_percent': (i * 17) % 100,
            'uptime_days': i * 7 % 365,
            
            # Interface data
            'interfaces': {
                f'GigabitEthernet1/0/{j}': {
                    'status': 'up' if (i + j) % 4 != 0 else 'down',
                    'speed': '1000',
                    'duplex': 'full',
                    'description': f'Link to device-{(i+j) % num_devices}',
                    'input_errors': (i * j) % 10000,
                    'output_errors': (i * j * 2) % 10000,
                }
                for j in range(8)  # 8 interfaces per device
            },
            
            # BGP neighbors (for routers)
            'bgp_neighbors': [
                {
                    'peer_ip': f'10.1.{i}.{j}',
                    'peer_as': 65000 + (i + j) % 100,
                    'state': 'Established' if (i + j) % 7 != 0 else 'Idle',
                    'prefixes_received': (i * j * 10) % 10000 if (i + j) % 7 != 0 else 0,
                    'uptime': f'{(i + j) % 30}d{(i * j) % 24}h'
                }
                for j in range(4)
            ] if device_type == 'router' else [],
            
            # Configuration snippets
            'snmp_community': 'public' if i % 10 == 0 else f'secure-{i}',
            'ntp_configured': i % 2 == 0,
            'ntp_servers': ['10.0.0.100', '10.0.0.101'] if i % 2 == 0 else [],
            'syslog_configured': i % 3 == 0,
            'syslog_server': '10.0.0.200' if i % 3 == 0 else None,
            
            # Security settings
            'ssh_enabled': True,
            'ssh_version': 2 if i % 8 != 0 else 1,
            'telnet_enabled': i % 15 == 0,
            'password_encryption': 'strong' if i % 5 != 0 else 'weak',
            
            # Alerts
            'active_alerts': [
                f'High CPU: {(i * 13) % 100}%' if (i * 13) % 100 > 85 else None,
                f'Low memory: {100 - (i * 17) % 100}% free' if (i * 17) % 100 > 90 else None,
                'Interface flapping on Gi1/0/1' if i % 12 == 0 else None,
                'BGP neighbor down' if device_type == 'router' and i % 7 == 0 else None,
            ]
        }
        
        # Clean up None alerts
        device_facts[device_ip]['active_alerts'] = [
            a for a in device_facts[device_ip]['active_alerts'] if a is not None
        ]
    
    return device_facts


def example_usage():
    """Example: Use RLMMiddleware in Deep Agent."""
    print("\n" + "="*80)
    print("EXAMPLE: Security Audit with RLMMiddleware")
    print("="*80)
    
    # Note: You need to set up your LLM first
    # Uncomment and configure:
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    
    device_facts = generate_sample_network_data(200)
    
    # Initialize Middleware with context (or use rlm_load_context tool dynamically)
    rlm_middleware = RLMMiddleware(
        model=ChatOpenAI(model="gpt-3.5-turbo"),
        initial_context=device_facts,
        config=RLMConfig(max_iteration=10, max_recursion_depth=1)
    )
    
    # Create Agent
    agent = create_deep_agent(
        model=ChatOpenAI(model="gpt-4"),
        middleware=[rlm_middleware],
        tools=[] # RLM tools are accepted automatically by the middleware or added to agent
    )
    
    query = '''
    Perform a security audit and identify:
    1. Devices using default SNMP community 'public'
    2. Devices with SSH version 1 enabled
    3. Devices with Telnet enabled
    4. Devices using weak password encryption
    '''
    
    # Run Agent
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    
    print("\nSecurity Audit Results:")
    print(result['messages'][-1].content)
    """
    
    print("(Set up your LLM and uncomment code above to run)")


def save_sample_data():
    """Generate and save sample data for testing."""
    print("\nGenerating sample network data...")
    device_facts = generate_sample_network_data(200)
    
    with open('sample_network_data.json', 'w') as f:
        json.dump(device_facts, f, indent=2)
    
    print(f"✓ Generated data for {len(device_facts)} devices")
    print(f"✓ Total size: {len(json.dumps(device_facts)):,} characters")
    print("✓ Saved to: sample_network_data.json")
    
    # Print summary
    print("\nData Summary:")
    print(f"  - Routers: {sum(1 for d in device_facts.values() if d['type'] == 'router')}")
    print(f"  - Switches: {sum(1 for d in device_facts.values() if d['type'] == 'switch')}")
    print(f"  - Firewalls: {sum(1 for d in device_facts.values() if d['type'] == 'firewall')}")


if __name__ == "__main__":
    print("="*80)
    print("RLM Network Device Analysis Examples")
    print("="*80)
    
    # Generate sample data
    save_sample_data()
    
    example_usage()
    
    print("\n" + "="*80)
    print("Next Steps:")
    print("="*80)
    print("1. Install dependencies")
    print("2. Set API key")
    print("3. Uncomment and run the example!")
    print("="*80)
