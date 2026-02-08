---
name: ansible-for-networks
description: Comprehensive network device automation using Ansible. Use when the agent needs to work with Ansible playbooks, inventories, or configurations for network devices (routers, switches, firewalls). Covers Cisco IOS/NX-OS/ASA, Juniper Junos, Arista EOS, and other network platforms. Use for creating playbooks, managing device configurations, gathering facts, troubleshooting network automation, or working with network modules.
---

# Ansible Network Automation

This skill provides guidance for creating, managing, and troubleshooting Ansible automation for network devices.

## Core Principles

## our organization operational mode 
when creating the ansible yaml file follow the principles in this listed below but create yaml file and wait for the review. you may need to know the model of devices to create the yaml file. In such cases, connecting to the devices management IP and checking the device model will help you to know the model of the device. In future we will have our ansible repository so the change will have to be created in a yaml file and added to the repo.

### Connection Methods

Network devices use specialized connection plugins instead of SSH:
- `network_cli`: CLI over SSH (most common)
- `netconf`: NETCONF protocol (Juniper, Cisco)
- `httpapi`: REST API (Arista, some Cisco)
- `local`: Delegation to localhost (legacy)

### Authentication Pattern

Network playbooks require credentials in inventory or group_vars:

```yaml
ansible_connection: network_cli
ansible_network_os: ios  # or nxos, eos, junos, etc.
ansible_user: admin
ansible_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256...
ansible_become: yes
ansible_become_method: enable
ansible_become_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256...
```

### Idempotency

Always use platform-specific modules (e.g., `cisco.ios.ios_config`) over raw commands. These modules check device state before making changes.

## Quick Start Patterns

### Basic Configuration Push

```yaml
---
- name: Configure network devices
  hosts: switches
  gather_facts: no
  
  tasks:
    - name: Configure VLANs
      cisco.ios.ios_vlans:
        config:
          - vlan_id: 10
            name: USERS
          - vlan_id: 20
            name: SERVERS
        state: merged
```

### Backup Configurations

```yaml
- name: Backup device configs
  hosts: all_network
  gather_facts: no
  
  tasks:
    - name: Backup running config
      cisco.ios.ios_config:
        backup: yes
        backup_options:
          filename: "{{ inventory_hostname }}_{{ ansible_date_time.date }}.cfg"
          dir_path: ./backups/
```

### Gather Device Facts

```yaml
- name: Collect network facts
  hosts: routers
  gather_facts: no
  
  tasks:
    - name: Gather IOS facts
      cisco.ios.ios_facts:
        gather_subset:
          - hardware
          - interfaces
      
    - name: Display model
      debug:
        msg: "{{ ansible_net_model }}"
```

## Platform-Specific Modules

### Cisco IOS/IOS-XE

Collection: `cisco.ios`

Key modules:
- `ios_config`: Configuration management
- `ios_command`: Execute commands
- `ios_vlans`: VLAN configuration
- `ios_interfaces`: Interface management
- `ios_l3_interfaces`: L3 interface configuration
- `ios_static_routes`: Static routing
- `ios_acls`: Access control lists
- `ios_facts`: Gather device information

Example:
```yaml
- name: Configure interface
  cisco.ios.ios_interfaces:
    config:
      - name: GigabitEthernet1/0/1
        description: Uplink to Core
        enabled: yes
    state: merged
```

### Cisco NX-OS

Collection: `cisco.nxos`

Key modules: Similar naming (`nxos_config`, `nxos_vlans`, etc.)

Example:
```yaml
- name: Configure VXLAN
  cisco.nxos.nxos_vxlan_vtep:
    interface: nve1
    host_reachability: yes
    source_interface: Loopback0
```

### Cisco ASA

Collection: `cisco.asa`

Example:
```yaml
- name: Configure ACL
  cisco.asa.asa_acls:
    config:
      - acls:
          - name: OUTSIDE_IN
            acl_type: extended
            aces:
              - grant: permit
                protocol: tcp
                source:
                  address: any
                destination:
                  address: 10.1.1.10
                  port_protocol:
                    eq: 443
```

### Juniper Junos

Collection: `junipernetworks.junos`

Connection: `netconf`

Example:
```yaml
- name: Configure interfaces
  junipernetworks.junos.junos_interfaces:
    config:
      - name: ge-0/0/1
        description: "Link to Switch"
        enabled: true
    state: merged
```

### Arista EOS

Collection: `arista.eos`

Example:
```yaml
- name: Configure BGP
  arista.eos.eos_bgp_global:
    config:
      as_number: 65001
      router_id: 10.0.0.1
      neighbors:
        - neighbor: 10.0.0.2
          remote_as: 65002
```

## Inventory Structure

### Directory Layout

```
inventory/
├── hosts
├── group_vars/
│   ├── all.yml
│   ├── routers.yml
│   ├── switches.yml
│   └── firewalls.yml
└── host_vars/
    ├── router1.yml
    └── router2.yml
```

### Sample Inventory

```ini
# inventory/hosts
[routers]
router1 ansible_host=192.168.1.1
router2 ansible_host=192.168.1.2

[switches]
switch1 ansible_host=192.168.1.10
switch2 ansible_host=192.168.1.11

[firewalls]
asa1 ansible_host=192.168.1.100

[routers:vars]
ansible_network_os=ios

[switches:vars]
ansible_network_os=ios

[firewalls:vars]
ansible_network_os=asa
```

### Group Variables

```yaml
# group_vars/all.yml
ansible_connection: network_cli
ansible_user: ansible
ansible_password: "{{ vault_ansible_password }}"
ansible_become: yes
ansible_become_method: enable
ansible_become_password: "{{ vault_enable_password }}"

# SSH settings
ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
```

## Common Patterns

### Configuration Templates

Use Jinja2 templates for complex configs:

```yaml
- name: Apply interface configuration
  cisco.ios.ios_config:
    src: templates/interface.j2
    
# templates/interface.j2
interface {{ interface_name }}
 description {{ interface_description }}
 ip address {{ ip_address }} {{ subnet_mask }}
 no shutdown
```

### Conditional Configuration

```yaml
- name: Configure HSRP
  cisco.ios.ios_config:
    lines:
      - standby 1 ip {{ hsrp_vip }}
      - standby 1 priority {{ hsrp_priority }}
      - standby 1 preempt
    parents: interface {{ interface }}
  when: hsrp_enabled | default(false)
```

### Configuration Blocks

```yaml
- name: Configure OSPF
  cisco.ios.ios_config:
    parents: router ospf 1
    lines:
      - network 10.0.0.0 0.255.255.255 area 0
      - passive-interface default
      - no passive-interface GigabitEthernet0/0
```

### Save Configuration

```yaml
- name: Save running config to startup
  cisco.ios.ios_config:
    save_when: modified
```

### Configuration Validation

```yaml
- name: Apply and verify config
  cisco.ios.ios_config:
    src: acl_config.j2
    match: strict
    replace: block
    after:
      - exit
  register: config_result
  
- name: Verify config applied
  assert:
    that:
      - config_result.changed == true
```

## Troubleshooting Patterns

### Debug Connection

```yaml
- name: Test connectivity
  cisco.ios.ios_command:
    commands:
      - show version
  register: version_output
  
- debug:
    var: version_output.stdout_lines
```

### Conditional Debugging

```yaml
- name: Gather interface status
  cisco.ios.ios_command:
    commands: show ip interface brief
  register: int_status
  
- debug:
    msg: "{{ int_status.stdout_lines }}"
  when: ansible_verbosity >= 2
```

### Error Handling

```yaml
- name: Configure with error handling
  block:
    - name: Apply configuration
      cisco.ios.ios_config:
        lines: "{{ config_lines }}"
  rescue:
    - name: Log failure
      debug:
        msg: "Configuration failed on {{ inventory_hostname }}"
    - name: Attempt rollback
      cisco.ios.ios_config:
        lines: "{{ rollback_commands }}"
  always:
    - name: Verify device reachable
      cisco.ios.ios_command:
        commands: show clock
```

## Ansible Vault for Credentials

### Create Vault File

```bash
ansible-vault create group_vars/all/vault.yml
```

### Vault Content

```yaml
vault_ansible_password: SecurePassword123
vault_enable_password: EnablePassword456
```

### Run with Vault

```bash
ansible-playbook -i inventory/hosts site.yml --ask-vault-pass
```

## Best Practices

### Pre-flight Checks

Always gather facts first to verify connectivity:

```yaml
- name: Pre-flight checks
  hosts: all
  gather_facts: no
  
  tasks:
    - name: Test reachability
      wait_for:
        host: "{{ ansible_host }}"
        port: 22
        timeout: 10
```

### Limit Parallelism

Network devices can be overwhelmed by parallel connections:

```yaml
- name: Configure devices
  hosts: all_network
  serial: 5  # Only 5 devices at a time
```

### Use Check Mode

Test playbooks without making changes:

```bash
ansible-playbook site.yml --check --diff
```

### Configuration Backup Before Changes

```yaml
- name: Backup before changes
  cisco.ios.ios_config:
    backup: yes
  delegate_to: localhost
  
- name: Apply changes
  cisco.ios.ios_config:
    src: new_config.j2
```

### Structured Configuration Management

Use resource modules (modern approach):

```yaml
# Preferred
- cisco.ios.ios_vlans:
    config: "{{ vlans }}"
    state: merged

# Avoid (legacy)
- cisco.ios.ios_config:
    lines: "vlan {{ item }}"
  loop: "{{ vlan_ids }}"
```

## Common Pitfalls

1. **Not using `gather_facts: no`**: Network modules don't use standard facts gathering
2. **Wrong connection plugin**: Use `network_cli`, not `ssh`
3. **Missing become settings**: Many devices need privilege escalation
4. **Hardcoded credentials**: Always use Ansible Vault
5. **No error handling**: Network changes can fail; use blocks/rescue
6. **Ignoring idempotency**: Check current state before changes
7. **Parallel execution**: Can overwhelm devices; use `serial` or `throttle`

## Collection Installation

Install required collections:

```bash
ansible-galaxy collection install cisco.ios
ansible-galaxy collection install cisco.nxos
ansible-galaxy collection install cisco.asa
ansible-galaxy collection install junipernetworks.junos
ansible-galaxy collection install arista.eos
```

Or use requirements.yml:

```yaml
---
collections:
  - name: cisco.ios
  - name: cisco.nxos
  - name: junipernetworks.junos
  - name: arista.eos
```

```bash
ansible-galaxy collection install -r requirements.yml
```

## Complete Example Playbook

```yaml
---
- name: Network Device Management
  hosts: all_network
  gather_facts: no
  serial: 10
  
  tasks:
    - name: Ensure device is reachable
      wait_for:
        host: "{{ ansible_host }}"
        port: 22
        timeout: 30
      delegate_to: localhost
      
    - name: Backup configurations
      block:
        - name: Create backup
          cisco.ios.ios_config:
            backup: yes
            backup_options:
              filename: "{{ inventory_hostname }}.cfg"
              dir_path: "./backups/{{ ansible_date_time.date }}"
      rescue:
        - debug:
            msg: "Backup failed for {{ inventory_hostname }}"
    
    - name: Gather device facts
      cisco.ios.ios_facts:
        gather_subset: all
      
    - name: Display device info
      debug:
        msg: "{{ inventory_hostname }}: {{ ansible_net_model }} running {{ ansible_net_version }}"
      
    - name: Configure VLANs
      cisco.ios.ios_vlans:
        config: "{{ vlans }}"
        state: merged
      when: vlans is defined
      notify: save config
      
  handlers:
    - name: save config
      cisco.ios.ios_config:
        save_when: modified
```

## Testing Strategy

1. **Syntax check**: `ansible-playbook --syntax-check playbook.yml`
2. **Check mode**: `ansible-playbook --check playbook.yml`
3. **Limit to test device**: `ansible-playbook -l test-router playbook.yml`
4. **Increase verbosity**: `ansible-playbook -vvv playbook.yml`
5. **Verify idempotency**: Run twice, second run should show no changes

## Performance Optimization

### Use Strategy Plugins

```yaml
- name: Fast execution
  hosts: switches
  strategy: free  # Don't wait for all hosts
  gather_facts: no
```

### Connection Persistence

```yaml
# ansible.cfg
[persistent_connection]
connect_timeout = 30
command_timeout = 30
```

### Disable Fact Caching for Network

```yaml
# ansible.cfg
[defaults]
gathering = explicit
```

## When Creating Network Playbooks

1. Start with small test devices
2. Always include backup tasks
3. Use check mode first
4. Implement error handling with block/rescue
5. Validate configuration after changes
6. Document device-specific requirements
7. Use platform-specific modules, not raw/command modules
8. Store credentials in Ansible Vault
9. Test idempotency
10. Consider rollback procedures
