---
name: network-design-document
description: our enterprise network infrastructure knowledge including network topology, IP addressing schemes, VLAN configurations, monitoring tools, and security zones. Use when troubleshooting network issues, planning network changes, documenting infrastructure, or analyzing network security and performance.
license: MIT
compatibility: Requires network access for monitoring tools. Best used with bash, python, and network utilities (ping, traceroute, nslookup, curl).
metadata:
  author: enterprise-it
  version: "1.0"
  last-updated: "2026-01"
  network-type: "multi-site-enterprise"
allowed-tools: Bash(ping:*) Bash(traceroute:*) Bash(nslookup:*) Bash(curl:*) Read
---

# Enterprise Network Infrastructure

## Overview

This skill provides comprehensive knowledge of the enterprise network infrastructure, including topology, addressing schemes, monitoring systems, and operational procedures.

## Network Architecture

### High-Level Topology

```
Internet
    |
[Edge Firewall Cluster]
    |
[Core Network - Datacenter]
    |
    +--- [Branch Offices] (MPLS/SD-WAN)
    +--- [Cloud Connectivity] (AWS/Azure)
    +--- [Remote Access VPN]
    +--- [DMZ/Public Services]
```

### Network Segments

The enterprise network is divided into several logical and physical segments:

#### 1. **Datacenter Network**
- **Purpose**: Primary data hosting, applications, databases, and core services
- **Location**: Primary DC in headquarters
- **Subnet Range**: `10.0.0.0/16`
- **VLAN Structure**:
  - VLAN 10: Management (`10.0.10.0/24`)
  - VLAN 20: Application Servers (`10.0.20.0/23`)
  - VLAN 30: Database Servers (`10.0.30.0/24`)
  - VLAN 40: Storage Network (`10.0.40.0/24`)
  - VLAN 50: Backup Network (`10.0.50.0/24`)

#### 2. **Branch Offices**
- **Purpose**: Regional office connectivity
- **Connectivity**: MPLS primary, SD-WAN secondary
- **Subnet Range**: `10.100.0.0/16` (subdivided by branch)

**Branch Allocation Schema**:
- Branch 01 - New York: `10.100.1.0/24`
- Branch 02 - London: `10.100.2.0/24`
- Branch 03 - Singapore: `10.100.3.0/24`
- Branch 04 - Sydney: `10.100.4.0/24`
- Branch 05 - Toronto: `10.100.5.0/24`
- Branches 06-99: `10.100.6.0/24` to `10.100.99.0/24` (reserved)

**Standard Branch VLANs**:
- VLAN 100: User Workstations (`10.100.X.0/25`)
- VLAN 101: Voice/VoIP (`10.100.X.128/26`)
- VLAN 102: Printers/IoT (`10.100.X.192/26`)

#### 3. **DMZ (Demilitarized Zone)**
- **Purpose**: Public-facing services and external access
- **Subnet Range**: `172.16.0.0/16`
- **VLAN Structure**:
  - VLAN 200: Web Servers (`172.16.1.0/24`)
  - VLAN 201: Mail Servers (`172.16.2.0/24`)
  - VLAN 202: DNS Servers (`172.16.3.0/24`)
  - VLAN 203: VPN Terminators (`172.16.4.0/24`)
  - VLAN 204: API Gateway (`172.16.5.0/24`)

#### 4. **Cloud Connectivity**
- **Purpose**: Hybrid cloud integration
- **AWS VPC Range**: `10.200.0.0/16`
- **Azure VNet Range**: `10.201.0.0/16`
- **Transit Gateway**: `10.250.0.0/24`

#### 5. **Management Network**
- **Purpose**: Out-of-band management, IPMI, ILO
- **Subnet Range**: `192.168.0.0/16`
- **VLAN Structure**:
  - VLAN 999: Network Device Management (`192.168.1.0/24`)
  - VLAN 998: Server IPMI/ILO (`192.168.2.0/24`)
  - VLAN 997: Security Appliances (`192.168.3.0/24`)

#### 6. **Guest/WiFi Network**
- **Purpose**: Guest and contractor access
- **Subnet Range**: `10.50.0.0/16`
- **Isolation**: Fully segmented, internet-only access
- **VLAN**: VLAN 150

## Key Network Infrastructure Components

### Core Routers
- **Primary Core Router**: `core-rtr-01.corp.local` (`10.0.10.1`)
- **Secondary Core Router**: `core-rtr-02.corp.local` (`10.0.10.2`)
- **Model**: Cisco Catalyst 9600 Series
- **Routing Protocol**: OSPF Area 0 (backbone)
- **Redundancy**: HSRP/VRRP configured

### Distribution Switches
- **DC-DIST-01**: `10.0.10.10` (Primary datacenter distribution)
- **DC-DIST-02**: `10.0.10.11` (Secondary datacenter distribution)
- **Model**: Cisco Nexus 9300 Series
- **Protocol**: VPC (Virtual Port Channel)

### Firewalls
- **Edge Firewall Cluster**:
  - Primary: `edge-fw-01.corp.local` (`172.16.0.1`)
  - Secondary: `edge-fw-02.corp.local` (`172.16.0.2`)
  - Platform: Palo Alto PA-5000 Series
  - HA Mode: Active/Passive
  
- **Internal Firewall**:
  - `internal-fw-01.corp.local` (`10.0.10.20`)
  - Platform: Fortinet FortiGate 1500D

### Load Balancers
- **Primary LB**: `lb-01.corp.local` (`10.0.20.5`)
- **Secondary LB**: `lb-02.corp.local` (`10.0.20.6`)
- **Platform**: F5 BIG-IP
- **VIPs**: Various application virtual IPs in `10.0.21.0/24`

### DNS Servers
- **Internal DNS**:
  - Primary: `dns-01.corp.local` (`10.0.10.53`)
  - Secondary: `dns-02.corp.local` (`10.0.10.54`)
  
- **DMZ DNS**:
  - Primary: `dns-dmz-01.corp.local` (`172.16.3.1`)
  - Secondary: `dns-dmz-02.corp.local` (`172.16.3.2`)

### DHCP Servers
- **Datacenter DHCP**: `10.0.10.67-68`
- **Branch DHCP**: Configured per-branch on local infrastructure

## Network Monitoring and Management Tools

### Primary Monitoring Platform

#### 1. **Network Management System (NMS)**
- **Tool**: SolarWinds Network Performance Monitor (NPM)
- **Console URL**: `https://nms.corp.local`
- **Server**: `10.0.10.100`
- **Monitors**:
  - Device availability (ICMP, SNMP)
  - Interface utilization and errors
  - Bandwidth consumption
  - Packet loss and latency
  - CPU and memory on network devices

#### 2. **Log Aggregation**
- **Tool**: Splunk Enterprise
- **Console URL**: `https://splunk.corp.local`
- **Server**: `10.0.10.110`
- **Collects**:
  - Firewall logs (all security events)
  - Switch/router syslogs
  - VPN authentication logs
  - Network device configuration changes
  - IDS/IPS alerts

#### 3. **Flow Analysis**
- **Tool**: Plixer Scrutinizer (NetFlow/sFlow)
- **Console URL**: `https://netflow.corp.local`
- **Server**: `10.0.10.120`
- **Analysis**:
  - Top talkers identification
  - Application traffic breakdown
  - Bandwidth hogs detection
  - Anomaly detection
  - Historical traffic trends

#### 4. **Network Configuration Management**
- **Tool**: Cisco Prime Infrastructure
- **Console URL**: `https://prime.corp.local`
- **Server**: `10.0.10.130`
- **Functions**:
  - Configuration backup and versioning
  - Compliance auditing
  - Change tracking
  - Template-based provisioning

#### 5. **Packet Capture and Analysis**
- **Tool**: Wireshark + SPAN ports
- **Dedicated Capture Server**: `10.0.10.140`
- **Remote Analysis**: Via SSH + tcpdump

#### 6. **IPAM (IP Address Management)**
- **Tool**: Infoblox DDI (DNS, DHCP, IPAM)
- **Console URL**: `https://ipam.corp.local`
- **Server**: `10.0.10.150`

#### 7. **Security Monitoring**
- **SIEM**: IBM QRadar
- **Console URL**: `https://siem.corp.local`
- **Server**: `10.0.10.160`
- **IDS/IPS**: Snort on dedicated appliances (`10.0.10.170-172`)

### Alerting and Notification

**Alert Priority Levels**:
- **P1 (Critical)**: Complete site outage, core router failure
  - Notification: PagerDuty + SMS + Email
  - Response Time: 15 minutes
  
- **P2 (High)**: Single link failure, degraded performance
  - Notification: PagerDuty + Email
  - Response Time: 1 hour
  
- **P3 (Medium)**: Non-critical service impact
  - Notification: Email + Ticket
  - Response Time: 4 hours
  
- **P4 (Low)**: Informational alerts
  - Notification: Ticket only
  - Response Time: Next business day

**Key Contacts**:
- Network Operations Center (NOC): `noc@corp.local`
- Network Engineering: `neteng@corp.local`
- Security Team: `security@corp.local`
- On-call Rotation: Managed in PagerDuty

## IP Addressing Standards

### Allocation Strategy
- **10.0.0.0/8**: Internal enterprise use (RFC1918)
  - `10.0.0.0/16`: Datacenter
  - `10.50.0.0/16`: Guest networks
  - `10.100.0.0/16`: Branch offices
  - `10.200-249.0.0/16`: Cloud and external connectivity
  - `10.250.0.0/16`: Future expansion
  
- **172.16.0.0/12**: DMZ and semi-public services
  
- **192.168.0.0/16**: Management networks

### Subnet Sizing Guidelines
- **/24 subnets**: Standard for most VLANs (254 usable IPs)
- **/23 subnets**: High-density user networks or server farms
- **/26 subnets**: Small branch offices or isolated segments
- **/30 subnets**: Point-to-point links between routers

### Reserved Addresses
- **x.x.x.1**: Default gateway (first usable IP)
- **x.x.x.2-5**: Reserved for redundancy (HSRP, VRRP virtual IPs)
- **x.x.x.250-254**: Reserved for infrastructure (DNS, NTP, etc.)
- **x.x.x.255**: Broadcast address

## Security Zones and Policies

### Zone Definitions

1. **Trusted Zone**: Internal datacenter and management networks
2. **Semi-Trusted Zone**: Branch offices and authenticated users
3. **Untrusted Zone**: Internet and DMZ
4. **Restricted Zone**: PCI/compliance environments (if applicable)

### Firewall Policy Summary

**Default Policies**:
- Trusted → Semi-Trusted: Allow with logging
- Trusted → Untrusted: Allow with deep inspection
- Semi-Trusted → Trusted: Deny (explicit rules required)
- Untrusted → Trusted: Deny all
- DMZ → Trusted: Deny (reverse proxy only)

**Common Allow Rules**:
- Branch → Datacenter: Business applications (TCP/443, TCP/3389, etc.)
- All Internal → Internet: Web (TCP/80, TCP/443) via proxy
- DMZ → Internet: SMTP, DNS, NTP
- Management Network → All: SSH (TCP/22), SNMP (UDP/161)

## Routing Configuration

### Internal Routing
- **Protocol**: OSPF (Open Shortest Path First)
- **OSPF Areas**:
  - Area 0 (Backbone): Datacenter core
  - Area 1: Branch offices (stub area)
  - Area 2: DMZ
  
### External Routing
- **Protocol**: BGP (Border Gateway Protocol)
- **AS Number**: 65000 (private ASN)
- **Peers**:
  - ISP 1: Primary internet (AS 701)
  - ISP 2: Backup internet (AS 3356)
  - MPLS Provider: (AS 65100)

### Static Routes
- Default route to edge firewalls: `0.0.0.0/0 → 172.16.0.1`
- Cloud connectivity: Managed via VPN tunnels and BGP

## Wireless Network

### WiFi Infrastructure
- **Controller**: Cisco WLC 5520 (`10.0.10.200`)
- **SSIDs**:
  - `Corp-Enterprise`: 802.1X authentication (VLAN 100-series per branch)
  - `Corp-Guest`: Web portal authentication (VLAN 150)
  - `Corp-IoT`: Pre-shared key (VLAN 102)

### Access Points
- **Model**: Cisco Catalyst 9100 Series (WiFi 6/6E)
- **Management**: Centralized via WLC
- **Deployment**: High-density coverage in offices, standard in branches

## VPN Configuration

### Remote Access VPN
- **Platform**: Cisco AnyConnect SSL VPN
- **Concentrators**:
  - `vpn-01.corp.local` (`172.16.4.10`)
  - `vpn-02.corp.local` (`172.16.4.11`)
- **Address Pool**: `10.99.0.0/16`
- **Authentication**: RADIUS + MFA (Duo Security)

### Site-to-Site VPN
- **Type**: IPsec tunnels
- **Endpoints**: All branch offices and cloud environments
- **Backup**: SD-WAN with automatic failover

## Troubleshooting Procedures

### Common Issue Resolution

#### Network Connectivity Issues
1. Verify physical layer (link status, cable integrity)
2. Check VLAN assignment and trunk configuration
3. Verify routing table entries (`show ip route`)
4. Test with ping/traceroute from multiple sources
5. Review firewall logs for blocks
6. Check for MAC address conflicts or IP duplicates

#### Performance Degradation
1. Check interface utilization in SolarWinds NPM
2. Review NetFlow data for top talkers
3. Analyze QoS statistics and dropped packets
4. Check for routing loops or suboptimal paths
5. Review recent configuration changes in Prime
6. Check for broadcast storms or spanning-tree issues

#### Security Incidents
1. Isolate affected segment immediately
2. Pull firewall and IDS logs from Splunk
3. Capture packets if active threat
4. Review QRadar SIEM for correlations
5. Engage security team via `security@corp.local`
6. Document in incident management system

## Network Change Management

### Change Process
1. Submit change request in ServiceNow
2. Impact assessment by network engineering
3. CAB (Change Advisory Board) approval for high-risk changes
4. Backup current configurations via Prime
5. Implement during maintenance window
6. Validate and document post-change
7. Rollback plan ready if needed

### Maintenance Windows
- **Standard**: Saturdays 02:00-06:00 local datacenter time
- **Emergency**: As needed with VP approval

## Compliance and Documentation

### Network Documentation
- **Visio Diagrams**: `\\fileserver\NetworkDocs\Diagrams\`
- **IP Spreadsheet**: Managed in Infoblox IPAM
- **Configuration Backups**: Daily automated via Prime
- **Runbooks**: `\\fileserver\NetworkDocs\Runbooks\`

### Compliance Requirements
- PCI-DSS: Segmented environment, logs retained 1 year
- SOX: Change management and audit trails
- GDPR: Data flow documentation, encryption requirements

## Useful Commands and Scripts

See `scripts/network-diagnostics.sh` for automated troubleshooting tools.

### Quick Diagnostics
```bash
# Test connectivity to core router
ping -c 4 10.0.10.1

# Trace path to external site
traceroute -n www.google.com

# Check DNS resolution
nslookup corp.local 10.0.10.53

# View active connections on monitoring server
ssh admin@10.0.10.100 "show active-connections"
```

### Monitoring Access
```bash
# SolarWinds NPM web console
https://nms.corp.local

# Splunk search for firewall blocks
https://splunk.corp.local
# Search: index=firewall action=blocked

# NetFlow top talkers
https://netflow.corp.local/reports/top-talkers
```

## Reference Files

- **Detailed Device Inventory**: See `references/DEVICE_INVENTORY.md`
- **VLAN Database**: See `references/VLAN_DATABASE.md`
- **Firewall Rule Matrix**: See `references/FIREWALL_RULES.md`
- **Network Diagrams**: See `assets/network-topology.png`
- **Emergency Contact List**: See `references/CONTACTS.md`

## Notes

- All IP addresses and hostnames in this document are placeholders
- Each enterprise should customize based on actual infrastructure
- Update monitoring tool URLs and credentials as appropriate
- Review and update quarterly or after major network changes
- Ensure backup documentation exists in multiple locations