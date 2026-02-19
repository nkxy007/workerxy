---
name: eve-ng-emulator
description: Automate EVE-NG network emulation lab creation, management, and topology deployment using evengsdk Python library and CLI. Use when you need to (1) Create or manage EVE-NG virtual network labs programmatically, (2) Deploy network topologies from YAML definitions, (3) Configure virtual network devices with templates or files, (4) Build automated test environments for network validation, (5) Manage nodes, networks, and links in EVE-NG labs, (6) Integrate network lab provisioning into CI/CD pipelines
license: Apache-2.0
metadata:
  author: eve-ng-skill
  version: "1.0"
  requires: evengsdk, Python 3.8+, EVE-NG instance
---

# EVE-NG Emulator Skill

## Overview

EVE-NG (Emulated Virtual Environment - Next Generation) is a powerful network emulation platform that allows you to create virtual network labs with routers, switches, firewalls, and other network devices. This skill enables you to programmatically manage EVE-NG labs using the `evengsdk` Python library and CLI tools.

**What this skill provides:**
- Automated lab creation and management
- Programmatic topology deployment
- Device configuration automation
- Integration with network automation workflows
- YAML-based declarative topology definitions

**Prerequisites:**
- EVE-NG instance (Community or Professional edition)
- Python 3.8 or higher
- Network access to EVE-NG API
- Valid EVE-NG credentials

## When to Use This Skill

Use this skill when you need to:

- **Automated Testing**: Create reproducible network labs for testing automation scripts
- **CI/CD Integration**: Deploy test topologies as part of continuous integration pipelines
- **Training Labs**: Quickly provision training environments with consistent configurations
- **Network Design Validation**: Test network designs before physical deployment
- **Rapid Prototyping**: Experiment with network architectures and protocols
- **Documentation**: Generate lab topologies from infrastructure-as-code definitions

## Installation & Setup

### Install evengsdk

```bash
# Install the library
pip install eve-ng

# Verify installation
eve-ng --help
```

### Configure Environment Variables

Create a `.env` file or export variables:

```bash
export EVE_NG_HOST=192.168.1.100
export EVE_NG_USERNAME=admin
export EVE_NG_PASSWORD=eve
export EVE_NG_PORT=80
export EVE_NG_PROTOCOL=http
export EVE_NG_SSL_VERIFY=False
export EVE_NG_LAB_PATH='/mylab.unl'
```

### Test Connectivity

```python
from evengsdk.client import EvengClient

# Create client
client = EvengClient("192.168.1.100", log_file="eve.log", ssl_verify=False)

# Disable SSL warnings for self-signed certificates
client.disable_insecure_warnings()

# Login
client.login(username="admin", password="eve")

# Test API access
templates = client.api.list_node_templates()
print(f"Available templates: {len(templates['data'])}")

# Logout
client.logout()
```

## Core Concepts

### Labs
- **Container** for network topology
- **Path**: Directory-like structure (e.g., `/`, `/projects/`)
- **File format**: `.unl` extension
- Contains nodes, networks, and links

### Nodes
- **Virtual devices**: Routers, switches, firewalls, servers
- **Templates**: Pre-configured device types (vEOS, CSR1000v, vIOS, etc.)
- **Properties**: Name, template, image, position, configuration
- **States**: Stopped, started, configured

### Networks
- **Connection points** for nodes
- **Types**:
  - `pnet0-9`: Bridge to physical networks (management)
  - `bridge`: Internal network segments
- **Visibility**: Controls display in topology

### Links
- **Connections** between nodes or nodes-to-networks
- **Types**:
  - Node-to-cloud: Management connections
  - Node-to-node: Point-to-point links
- **Labels**: Interface names (e.g., `Gi0/0`, `Eth1`)

### Templates
- **Device definitions** available in EVE-NG
- **Examples**: `veos`, `viosl2`, `csr1000v`, `nxosv9k`
- **Images**: Specific versions (e.g., `veos-4.22.0F`)

## Basic Operations

### 1. Lab Management

#### Create a Lab

```python
from evengsdk.client import EvengClient

client = EvengClient("192.168.1.100", ssl_verify=False)
client.login(username="admin", password="eve")

# Define lab
lab = {
    "name": "my_network_lab",
    "description": "Test Lab for Automation",
    "path": "/"
}

# Create lab
response = client.api.create_lab(**lab)
if response['status'] == "success":
    print(f"Lab created: {lab['name']}")
    lab_path = f"{lab['path']}{lab['name']}.unl"
else:
    print(f"Error: {response.get('message')}")

client.logout()
```

#### List Labs

```python
# List all labs
labs = client.api.list_labs()
for lab in labs['data']:
    print(f"Lab: {lab['name']} - Path: {lab['path']}")
```

#### Delete a Lab

```python
# Delete lab
lab_path = "/my_network_lab.unl"
response = client.api.delete_lab(lab_path)
```

### 2. Node Management

#### Add Nodes to Lab

```python
lab_path = "/my_network_lab.unl"

# Define nodes
nodes = [
    {
        "name": "spine01",
        "template": "veos",
        "image": "veos-4.22.0F",
        "left": 100,
        "top": 100
    },
    {
        "name": "leaf01",
        "template": "veos",
        "image": "veos-4.22.0F",
        "left": 50,
        "top": 300
    },
    {
        "name": "leaf02",
        "template": "veos",
        "image": "veos-4.22.0F",
        "left": 200,
        "top": 300
    }
]

# Add nodes to lab
for node in nodes:
    response = client.api.add_node(lab_path, **node)
    print(f"Added node: {node['name']}")
```

#### List Available Templates

```python
# Get all available node templates
templates = client.api.list_node_templates()
for template_name, template_desc in templates['data'].items():
    print(f"{template_name}: {template_desc}")
```

#### Start/Stop Nodes

```python
# Start all nodes in lab
client.api.start_all_nodes(lab_path)

# Stop all nodes
client.api.stop_all_nodes(lab_path)

# Start specific node
node_id = 1
client.api.start_node(lab_path, node_id)
```

### 3. Network Management

#### Create Management Network

```python
lab_path = "/my_network_lab.unl"

# Create management cloud (bridge to physical network)
mgmt_cloud = {
    "name": "mgmt-network",
    "network_type": "pnet1",  # Physical network bridge
    "visibility": 1
}

response = client.api.add_lab_network(lab_path, **mgmt_cloud)
print(f"Created network: {mgmt_cloud['name']}")
```

#### Create Internal Networks

```python
# Create internal network segments
internal_net = {
    "name": "internal-net",
    "network_type": "bridge",
    "visibility": 1
}

client.api.add_lab_network(lab_path, **internal_net)
```

### 4. Link Management

#### Connect Nodes to Management Network

```python
lab_path = "/my_network_lab.unl"

# Connect nodes to management cloud
mgmt_connections = [
    {"src": "spine01", "src_label": "Management1", "dst": "mgmt-network"},
    {"src": "leaf01", "src_label": "Management1", "dst": "mgmt-network"},
    {"src": "leaf02", "src_label": "Management1", "dst": "mgmt-network"}
]

for link in mgmt_connections:
    client.api.connect_node_to_cloud(lab_path, **link)
    print(f"Connected {link['src']} to {link['dst']}")
```

#### Create Point-to-Point Links

```python
# Create node-to-node connections
p2p_links = [
    {"src": "spine01", "src_label": "Ethernet1", "dst": "leaf01", "dst_label": "Ethernet1"},
    {"src": "spine01", "src_label": "Ethernet2", "dst": "leaf02", "dst_label": "Ethernet1"}
]

for link in p2p_links:
    client.api.connect_node_to_node(lab_path, **link)
    print(f"Connected {link['src']}:{link['src_label']} to {link['dst']}:{link['dst_label']}")
```

### 5. Configuration Deployment

#### Using Configuration Files

```python
# Deploy configuration from file
node_config = {
    "name": "leaf01",
    "config_file": "/path/to/configs/leaf01.cfg"
}

# Configuration will be applied when node starts
```

#### Using Jinja2 Templates

```python
# Deploy using Jinja2 template with variables
node_with_template = {
    "name": "leaf02",
    "template": "veos",
    "image": "veos-4.22.0F",
    "configuration": {
        "template": "base.j2",
        "vars": {
            "hostname": "leaf02",
            "management_ip": "10.0.0.2/24",
            "gateway": "10.0.0.1"
        }
    }
}
```

**Example Jinja2 Template** (`base.j2`):
```jinja2
hostname {{ hostname }}
!
interface Management1
   ip address {{ management_ip }}
   no shutdown
!
ip route 0.0.0.0/0 {{ gateway }}
```

## Topology Builder (YAML-based)

The topology builder allows you to define entire labs declaratively using YAML files.

### YAML Topology Format

```yaml
---
name: leaf-spine-lab
description: 2-Spine 4-Leaf Topology
path: "/"

nodes:
  - name: spine01
    template: veos
    image: veos-4.22.0F
    node_type: qemu
    left: 200
    top: 100
    configuration:
      template: spine.j2
      vars:
        hostname: spine01
        router_id: 1.1.1.1
        asn: 65001

  - name: spine02
    template: veos
    image: veos-4.22.0F
    node_type: qemu
    left: 400
    top: 100
    configuration:
      template: spine.j2
      vars:
        hostname: spine02
        router_id: 1.1.1.2
        asn: 65001

  - name: leaf01
    template: veos
    image: veos-4.22.0F
    node_type: qemu
    left: 100
    top: 300
    configuration:
      file: configs/leaf01.cfg

  - name: leaf02
    template: veos
    image: veos-4.22.0F
    node_type: qemu
    left: 250
    top: 300

networks:
  - name: mgmt-cloud
    network_type: pnet1
    visibility: 1
    top: 50
    left: 500

links:
  network:
    - {src: "spine01", src_label: "Management1", dst: "mgmt-cloud"}
    - {src: "spine02", src_label: "Management1", dst: "mgmt-cloud"}
    - {src: "leaf01", src_label: "Management1", dst: "mgmt-cloud"}
    - {src: "leaf02", src_label: "Management1", dst: "mgmt-cloud"}
  
  node:
    - {src: "spine01", src_label: "Ethernet1", dst: "leaf01", dst_label: "Ethernet1"}
    - {src: "spine01", src_label: "Ethernet2", dst: "leaf02", dst_label: "Ethernet1"}
    - {src: "spine02", src_label: "Ethernet1", dst: "leaf01", dst_label: "Ethernet2"}
    - {src: "spine02", src_label: "Ethernet2", dst: "leaf02", dst_label: "Ethernet2"}
```

### Deploy Topology from YAML

```bash
# Using CLI
eve-ng lab create-from-topology \
  -t topologies/leaf-spine-lab.yml \
  --template-dir templates/

# Using Python
from evengsdk.topology import TopologyBuilder

builder = TopologyBuilder(client)
builder.build_from_yaml("topologies/leaf-spine-lab.yml", template_dir="templates/")
```

## CLI Usage Examples

### Lab Commands

```bash
# List all labs
eve-ng --host 192.168.1.100 --username admin --password eve lab list

# Create lab
eve-ng lab create --name test-lab --path /

# Delete lab
eve-ng lab delete --path /test-lab.unl

# Show lab details
eve-ng lab show --path /test-lab.unl
```

### Node Commands

```bash
# List nodes in lab
eve-ng node list --lab-path /test-lab.unl

# Add node
eve-ng node add \
  --lab-path /test-lab.unl \
  --name router01 \
  --template vios \
  --image vios-15.6

# Start all nodes
eve-ng node start-all --lab-path /test-lab.unl

# Stop specific node
eve-ng node stop --lab-path /test-lab.unl --node-id 1
```

### System Commands

```bash
# List available templates
eve-ng list-node-templates

# List network types
eve-ng list-network-types

# Show server status
eve-ng show-status

# Get template details
eve-ng show-template --template veos
```

## Complete Example: Leaf-Spine Topology

```python
from evengsdk.client import EvengClient

def create_leaf_spine_lab():
    # Initialize client
    client = EvengClient("192.168.1.100", ssl_verify=False, protocol="http")
    client.disable_insecure_warnings()
    client.login(username="admin", password="eve")
    client.set_log_level("INFO")
    
    # Create lab
    lab = {
        "name": "leaf_spine_lab",
        "description": "2-Spine 4-Leaf EVPN/VXLAN Lab",
        "path": "/"
    }
    
    resp = client.api.create_lab(**lab)
    if resp['status'] != "success":
        print(f"Error creating lab: {resp}")
        return
    
    lab_path = f"{lab['path']}{lab['name']}.unl"
    print(f"Created lab: {lab_path}")
    
    # Create management network
    mgmt_cloud = {"name": "mgmt", "network_type": "pnet1"}
    client.api.add_lab_network(lab_path, **mgmt_cloud)
    print("Created management network")
    
    # Define spine switches
    spines = [
        {"name": "spine01", "template": "veos", "image": "veos-4.22.0F", "left": 200, "top": 100},
        {"name": "spine02", "template": "veos", "image": "veos-4.22.0F", "left": 400, "top": 100}
    ]
    
    # Define leaf switches
    leaves = [
        {"name": "leaf01", "template": "veos", "image": "veos-4.22.0F", "left": 100, "top": 300},
        {"name": "leaf02", "template": "veos", "image": "veos-4.22.0F", "left": 250, "top": 300},
        {"name": "leaf03", "template": "veos", "image": "veos-4.22.0F", "left": 400, "top": 300},
        {"name": "leaf04", "template": "veos", "image": "veos-4.22.0F", "left": 550, "top": 300}
    ]
    
    # Add all nodes
    all_nodes = spines + leaves
    for node in all_nodes:
        client.api.add_node(lab_path, **node)
        print(f"Added node: {node['name']}")
    
    # Connect all nodes to management
    for node in all_nodes:
        link = {"src": node['name'], "src_label": "Management1", "dst": "mgmt"}
        client.api.connect_node_to_cloud(lab_path, **link)
    print("Connected all nodes to management network")
    
    # Create spine-to-leaf links (full mesh)
    for spine in spines:
        for idx, leaf in enumerate(leaves, start=1):
            link = {
                "src": spine['name'],
                "src_label": f"Ethernet{idx}",
                "dst": leaf['name'],
                "dst_label": f"Ethernet{spines.index(spine) + 1}"
            }
            client.api.connect_node_to_node(lab_path, **link)
            print(f"Connected {link['src']}:{link['src_label']} to {link['dst']}:{link['dst_label']}")
    
    print("\n✅ Lab creation complete!")
    print(f"Lab path: {lab_path}")
    print(f"Total nodes: {len(all_nodes)}")
    
    client.logout()

if __name__ == "__main__":
    create_leaf_spine_lab()
```

## Common Patterns

### Hub-and-Spoke Topology

```python
def create_hub_spoke(client, lab_path):
    # Hub router
    hub = {"name": "hub-router", "template": "vios", "image": "vios-15.6", "left": 300, "top": 200}
    client.api.add_node(lab_path, **hub)
    
    # Spoke routers
    spokes = [
        {"name": f"spoke{i}", "template": "vios", "image": "vios-15.6", 
         "left": 100 + (i * 150), "top": 400}
        for i in range(1, 5)
    ]
    
    for spoke in spokes:
        client.api.add_node(lab_path, **spoke)
        
        # Connect spoke to hub
        link = {
            "src": "hub-router",
            "src_label": f"GigabitEthernet0/{spokes.index(spoke)}",
            "dst": spoke['name'],
            "dst_label": "GigabitEthernet0/0"
        }
        client.api.connect_node_to_node(lab_path, **link)
```

### Full Mesh Topology

```python
def create_full_mesh(client, lab_path, nodes):
    # Add all nodes
    for node in nodes:
        client.api.add_node(lab_path, **node)
    
    # Create full mesh connections
    interface_counter = {}
    for i, node1 in enumerate(nodes):
        interface_counter[node1['name']] = 0
        for node2 in nodes[i+1:]:
            link = {
                "src": node1['name'],
                "src_label": f"Ethernet{interface_counter[node1['name']]}",
                "dst": node2['name'],
                "dst_label": f"Ethernet{interface_counter.get(node2['name'], 0)}"
            }
            client.api.connect_node_to_node(lab_path, **link)
            interface_counter[node1['name']] += 1
            interface_counter[node2['name']] = interface_counter.get(node2['name'], 0) + 1
```

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to EVE-NG API

**Solutions**:
```python
# Check connectivity
import requests
response = requests.get("http://192.168.1.100/api/status")
print(response.status_code)

# Verify credentials
client = EvengClient("192.168.1.100")
try:
    client.login(username="admin", password="eve")
    print("✅ Login successful")
except Exception as e:
    print(f"❌ Login failed: {e}")
```

### Template Not Found

**Problem**: Error adding node - template not available

**Solution**:
```python
# List available templates
templates = client.api.list_node_templates()
available = [t for t in templates['data'].keys() if 'missing' not in templates['data'][t]]
print(f"Available templates: {available}")

# Check specific template
template_name = "veos"
if template_name in available:
    print(f"✅ Template {template_name} is available")
else:
    print(f"❌ Template {template_name} not found")
```

### Node Startup Failures

**Problem**: Nodes fail to start

**Checks**:
1. Verify image is uploaded to EVE-NG
2. Check EVE-NG server resources (CPU, RAM)
3. Review node console for errors
4. Verify template configuration

```bash
# Check EVE-NG server status
eve-ng show-status

# View node details
eve-ng node show --lab-path /test-lab.unl --node-id 1
```

### Authentication Errors

**Problem**: `401 Unauthorized` errors

**Solutions**:
```python
# Ensure proper login
client.login(username="admin", password="eve")

# Check session is active
# Re-login if needed after long idle periods

# Use environment variables for credentials
import os
username = os.getenv("EVE_NG_USERNAME")
password = os.getenv("EVE_NG_PASSWORD")
```

## Best Practices

### Lab Organization

1. **Use descriptive names**: `leaf-spine-evpn` not `lab1`
2. **Organize by path**: Group related labs in folders
3. **Version control**: Store YAML topologies in git
4. **Document purpose**: Use clear descriptions

### Naming Conventions

```python
# Good naming
nodes = [
    {"name": "core-router-01", ...},
    {"name": "access-switch-floor2", ...},
    {"name": "fw-dmz-primary", ...}
]

# Avoid generic names
nodes = [
    {"name": "router1", ...},
    {"name": "switch", ...},
    {"name": "device", ...}
]
```

### Resource Management

```python
# Stop nodes when not in use
client.api.stop_all_nodes(lab_path)

# Delete unused labs
client.api.delete_lab("/old-lab.unl")

# Monitor EVE-NG resources
status = client.api.get_server_status()
print(f"CPU: {status['cpu']}%, RAM: {status['ram']}%")
```

### Configuration Management

1. **Use templates**: Jinja2 for dynamic configs
2. **Separate data**: Keep variables in separate files
3. **Version control**: Track configuration changes
4. **Validate configs**: Test before deployment

```python
# Good: Separate data from template
config = {
    "template": "base.j2",
    "vars": "data/leaf01.yml"  # External variable file
}

# Better: Use version-controlled configs
config = {
    "file": "configs/v2.0/leaf01.cfg"
}
```

### Error Handling

```python
def safe_lab_creation(client, lab_config):
    try:
        response = client.api.create_lab(**lab_config)
        if response['status'] == 'success':
            return response
        else:
            print(f"Lab creation failed: {response.get('message')}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None
```

## Limitations & Gotchas

### EVE-NG Version Compatibility
- evengsdk works with EVE-NG Community and Professional
- API endpoints may vary between versions
- Always test with your specific EVE-NG version

### Resource Constraints
- Each node consumes CPU and RAM
- Monitor server resources before adding many nodes
- Consider node startup time in automation

### Template Availability
- Templates must be installed on EVE-NG server
- Image files must be uploaded separately
- Template names are case-sensitive

### Network Type Restrictions
- `pnet0-9`: Limited to 10 physical network bridges
- Network types depend on EVE-NG configuration
- Some network types require specific permissions

### API Rate Limiting
- Avoid rapid API calls in loops
- Use batch operations when possible
- Implement retry logic for transient failures

### Configuration Deployment
- Configurations apply on node startup
- Changes require node restart to take effect
- Template rendering happens server-side

## Integration Examples

### CI/CD Pipeline Integration

```yaml
# .gitlab-ci.yml example
test-network-automation:
  stage: test
  script:
    - pip install eve-ng ansible
    - eve-ng lab create-from-topology -t test-topology.yml
    - ansible-playbook -i eve-inventory.yml test-playbook.yml
    - eve-ng lab delete --path /test-topology.unl
  only:
    - merge_requests
```

### Ansible Integration

```yaml
# Ansible playbook to create EVE-NG lab
---
- name: Deploy EVE-NG Lab
  hosts: localhost
  tasks:
    - name: Create lab from topology
      command: >
        eve-ng lab create-from-topology
        -t {{ topology_file }}
        --template-dir {{ template_dir }}
      environment:
        EVE_NG_HOST: "{{ eve_host }}"
        EVE_NG_USERNAME: "{{ eve_user }}"
        EVE_NG_PASSWORD: "{{ eve_pass }}"
```

### Python Automation Framework

```python
class EVELabManager:
    def __init__(self, host, username, password):
        self.client = EvengClient(host, ssl_verify=False)
        self.client.login(username=username, password=password)
    
    def deploy_topology(self, yaml_file):
        """Deploy topology from YAML file"""
        # Implementation here
        pass
    
    def validate_connectivity(self, lab_path):
        """Validate all nodes are connected"""
        # Implementation here
        pass
    
    def cleanup(self, lab_path):
        """Stop and delete lab"""
        self.client.api.stop_all_nodes(lab_path)
        self.client.api.delete_lab(lab_path)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.logout()

# Usage
with EVELabManager("192.168.1.100", "admin", "eve") as manager:
    manager.deploy_topology("topology.yml")
    manager.validate_connectivity("/topology.unl")
```

## Additional Resources

- **evengsdk Documentation**: https://ttafsir.github.io/evengsdk/
- **EVE-NG Official**: https://www.eve-ng.net/
- **GitHub Repository**: https://github.com/ttafsir/evengsdk
- **Community Forum**: https://www.eve-ng.net/index.php/community/

## Quick Reference

### Common Commands

```bash
# Lab operations
eve-ng lab list
eve-ng lab create --name <name> --path <path>
eve-ng lab delete --path <lab_path>

# Node operations
eve-ng node list --lab-path <lab_path>
eve-ng node start-all --lab-path <lab_path>
eve-ng node stop-all --lab-path <lab_path>

# System info
eve-ng list-node-templates
eve-ng show-status
```

### Python Quick Start

```python
from evengsdk.client import EvengClient

# Connect
client = EvengClient("host", ssl_verify=False)
client.login(username="admin", password="eve")

# Create lab
client.api.create_lab(name="lab", description="desc", path="/")

# Add node
client.api.add_node("/lab.unl", name="r1", template="vios", image="vios-15.6")

# Create link
client.api.connect_node_to_node("/lab.unl", src="r1", src_label="Gi0/0", 
                                  dst="r2", dst_label="Gi0/0")

# Cleanup
client.logout()
```
