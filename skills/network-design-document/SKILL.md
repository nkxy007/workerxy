---
name: network-design-document
description: Living knowledge base of enterprise network infrastructure including topology, IP addressing, VLANs, monitoring tools, and security policies. Automatically updated as new network information is discovered during agent tasks.
license: MIT
compatibility: Requires network access for monitoring tools. Best used with bash, python, and network utilities.
metadata:
  author: enterprise-it
  version: "1.0.0"
  last-updated: "2026-02-17"
  auto-update: true
  update-policy: "auto-with-approval"
  total-updates: 0
allowed-tools: Bash(ping:*) Bash(traceroute:*) Bash(nslookup:*) Bash(curl:*) Read
---

# Network Design Documentation

> [!NOTE]
> This is a **living knowledge base** that automatically updates as the agent discovers new network infrastructure information during tasks. All updates are logged in the changelog below.

## 📋 Metadata & Change Tracking

**Last Updated**: 2026-02-17  
**Total Updates**: 0  
**Update Policy**: Auto-with-approval (agent proposes, user approves)  
**Status**: ✅ Active

### Recent Changes

<!-- Auto-generated changelog - most recent first -->
- **2026-02-17**: Initial skill creation

---

## 🏗️ Network Architecture

<!-- Dynamic section - updates when topology changes discovered -->

### High-Level Topology

> [!IMPORTANT]
> Network topology information will be automatically populated as the agent discovers infrastructure components.

**Status**: 🔍 Awaiting discovery

### Network Segments

<!-- Discovered network segments will appear here -->

**Discovered Segments**: 0

---

## 🖥️ Infrastructure Components

<!-- Dynamic section - updates when new devices discovered -->

### Core Routers

**Discovered Devices**: 0

<!-- Example format:
- **Hostname**: `core-rtr-01.corp.local`
- **IP Address**: `10.0.10.1`
- **Model**: Cisco Catalyst 9600 Series
- **Role**: Primary Core Router
- **Discovered**: 2026-02-17
-->

### Switches

**Discovered Devices**: 0

### Firewalls

**Discovered Devices**: 0

### Load Balancers

**Discovered Devices**: 0

### Other Network Devices

**Discovered Devices**: 0

---

## 🌐 IP Addressing & VLANs

<!-- Dynamic section - updates when IP schemes and VLANs discovered -->

### IP Address Allocation

**Discovered Subnets**: 0

<!-- Example format:
- **Subnet**: `10.0.10.0/24`
- **Purpose**: Management Network
- **VLAN**: 10
- **Discovered**: 2026-02-17
-->

### VLAN Configuration

**Discovered VLANs**: 0

<!-- Example format:
- **VLAN ID**: 10
- **Name**: Management
- **Subnet**: `10.0.10.0/24`
- **Purpose**: Network device management
- **Discovered**: 2026-02-17
-->

---

## 📊 Monitoring & Management Tools

<!-- Dynamic section - updates when monitoring tools discovered -->

### Network Management Systems

**Discovered Tools**: 0

<!-- Example format:
- **Tool**: SolarWinds Network Performance Monitor
- **URL**: `https://nms.corp.local`
- **Server IP**: `10.0.10.100`
- **Purpose**: Device availability, interface utilization, bandwidth monitoring
- **Discovered**: 2026-02-17
-->

### Log Aggregation

**Discovered Tools**: 0

### Flow Analysis

**Discovered Tools**: 0

### Security Monitoring

**Discovered Tools**: 0

---

## 🔒 Security Policies & Zones

<!-- Dynamic section - updates when security info discovered -->

### Security Zones

**Discovered Zones**: 0

<!-- Example format:
- **Zone**: Trusted
- **Networks**: Internal datacenter, management networks
- **Default Policy**: Allow with logging
- **Discovered**: 2026-02-17
-->

### Firewall Policies

**Discovered Policies**: 0

---

## 🔄 Routing Configuration

<!-- Dynamic section - updates when routing info discovered -->

### Routing Protocols

**Discovered Protocols**: 0

<!-- Example format:
- **Protocol**: OSPF
- **Areas**: Area 0 (Backbone - Datacenter)
- **Discovered**: 2026-02-17
-->

### BGP Configuration

**Status**: 🔍 Not yet discovered

---

## 📡 Wireless Network

<!-- Dynamic section - updates when WiFi info discovered -->

### WiFi Infrastructure

**Discovered Components**: 0

---

## 🔐 VPN Configuration

<!-- Dynamic section - updates when VPN info discovered -->

### Remote Access VPN

**Status**: 🔍 Not yet discovered

### Site-to-Site VPN

**Status**: 🔍 Not yet discovered

---

## 🛠️ Troubleshooting Procedures

<!-- Semi-static section - updates when new procedures learned -->

### Common Diagnostic Commands

```bash
# Test connectivity to a host
ping -c 4 <host>

# Trace network path
traceroute -n <host>

# Check DNS resolution
nslookup <hostname> <dns-server>

# Test HTTP/HTTPS connectivity
curl -I <url>
```

### Known Issues & Solutions

**Documented Issues**: 0

<!-- Example format:
- **Issue**: High latency on VLAN 20
- **Symptoms**: Slow application response times
- **Solution**: Check interface utilization, review QoS policies
- **Documented**: 2026-02-17
-->

---

## 📝 Pending Updates

<!-- Temporary section - holds unconfirmed information awaiting user approval -->

**Pending Updates**: 0

<!-- Updates will appear here before being approved and integrated into the main sections -->

---

## 📚 Reference Information

### Useful Links

- Network documentation repository: *To be discovered*
- Configuration backup location: *To be discovered*
- Runbook location: *To be discovered*

### Key Contacts

- Network Operations Center (NOC): *To be discovered*
- Network Engineering: *To be discovered*
- Security Team: *To be discovered*

---

## 🔧 Skill Configuration

This skill is configured to automatically update when the agent discovers:
- Network devices (routers, switches, firewalls, load balancers)
- IP addressing schemes and subnet allocations
- VLAN configurations
- Monitoring tools and dashboards
- Security policies and zones
- Routing protocols and configurations
- Troubleshooting procedures

**Update Mode**: Automatic with user approval  
**Confidence Threshold**: 75%  
**Prompt Timing**: Task completion

---

## 📖 Usage Notes

> [!TIP]
> This skill will automatically populate as you work with the agent on network-related tasks. The agent will propose updates at task completion, which you can approve or reject.

**How to use this skill**:
1. Execute network-related tasks normally
2. Agent will detect and extract network information
3. At task completion, review proposed updates
4. Approve updates to add them to this skill
5. Use `/skill` commands for manual management

**Manual update commands**:
- `/skill update network-design-document` - Manually trigger update
- `/skill review` - Review pending updates
- `/skill show` - Display this skill content
- `/skill rollback` - Undo last update

---

*This skill was created on 2026-02-17 and will evolve as network infrastructure is discovered and documented.*
