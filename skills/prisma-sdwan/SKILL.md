---
name: prisma-sdwan
description: Comprehensive guide for designing, deploying, operating, and troubleshooting Palo Alto Networks Prisma SD-WAN. Covers architecture, configuration, policies, routing, and operations.
license: Proprietary
metadata:
  version: "1.0"
---

# Prisma SD-WAN Skill

## Overview

This skill provides comprehensive guidance for designing, deploying, operating, and troubleshooting Palo Alto Networks Prisma SD-WAN environments. Prisma SD-WAN is a cloud-delivered, application-defined SD-WAN solution that forms a key component of the SASE (Secure Access Service Edge) framework.

## Core Architecture

### Components

**Cloud Controller (SaaS)**
- Single source of truth for policy configuration and network topology
- Centralized management via cloud-delivered portal (Strata Cloud Manager)
- Multi-tenant capable
- Zero-touch provisioning (ZTP) orchestration
- API-driven automation platform

**ION Devices (Data Plane)**
- Physical appliances: ION 1000, 1200, 2000, 3000, 3200, 5200, 7000, 9000, 9200 series
- Virtual appliances (vION): Available for AWS, Azure, GCP, Alibaba Cloud, KVM, VMware, OCI
- Hardware models with cellular: ION 1200-C, 1200-S-C (4G/5G)
- Temperature-hardened variants: ION 3200H

**ION Fabric**
- Overlay mesh of encrypted IPSec tunnels (AES-256)
- Multiple overlay types: Direct, Prisma SD-WAN VPN, Standard VPN
- Automatic tunnel establishment between sites
- Dynamic path selection based on application requirements

**Management Platforms**
- Strata Cloud Manager: Primary unified management interface
- Strata Multitenant Cloud Manager: MSP/multi-tenant management
- On-premises controller option available

### Deployment Modes

**Analytics Mode**
- ION device monitors traffic in-path
- Provides visibility and analytics
- No policy enforcement or path selection
- Used for baseline assessment

**Control Mode**
- Full SD-WAN functionality enabled
- Dynamic path selection
- Policy enforcement (QoS, Security, Path)
- Application steering and optimization

**Disabled Mode**
- ION device bypasses all traffic
- Used for maintenance or troubleshooting

## Design Principles

### Site Architecture Models

#### Branch Deployments

**Layer 2-Only Model**
- ION deployed in-line between switch and router
- Internet links terminate on ION
- Private WAN terminates on existing router
- Uses bypass pairs for private WAN
- Minimal routing configuration

**Layer 2/Layer 3 Model**
- ION in-line with L3 WAN interface capability
- WAN interfaces configured for L3 routing
- Supports BGP/OSPF peering with existing routers
- Requires "L3 Direct Private WAN Forwarding" enabled

**Router Replacement Model**
- ION terminates both private WAN and internet links
- ION participates in dynamic routing with edge router
- Advertises branch prefixes, learns core prefixes
- Maximum consolidation of branch hardware

#### Data Center Deployments

**BGP-Based DC Deployment (Off-Path)**
- ION connects to DC core router (off-path)
- Attracts traffic via more-specific BGP routes
- Only attracts Prisma SD-WAN branch traffic
- Supports core, edge, and classic BGP peers
- Requires BGP for HA scenarios

**OSPF-Based DC Deployment (In-Path)**
- ION placed in-path between private WAN and core router
- Supported from device version 6.4.1+
- OSPF adjacencies with LAN/core devices
- Route redistribution between BGP and OSPF

**DC Peer Types**
- **Core Peer**: DC core/LAN router (auto route-map generation)
- **Edge Peer**: WAN edge/MPLS PE router (auto route-map generation)
- **Classic Peer**: Manual route-map configuration required

### High Availability Design

**Branch HA**
- Dual ION devices at branch
- Active-active or active-backup
- Automatic failover
- Shared configuration via controller

**Data Center HA**
- Requires BGP on core/LAN side
- Host tracking for tunnel health monitoring
- Automatic tunnel failover to standby DC ION
- Integration with Azure Route Server (ARS) or AWS Transit Gateway

**Virtual ION HA**
- Deploy vION pairs in different availability zones
- Use CloudBlades for automated deployment (AWS Transit Gateway, Azure vWAN)
- Marketplace solution templates available

### Network Context and Segmentation

**Network Contexts**
- Segment traffic for different policy treatment
- Highest precedence in policy evaluation
- Examples: Guest, Corporate, Voice, IoT
- Attached to LAN networks/interfaces
- Enables micro-segmentation without VRFs

**Security Zones**
- Define enforcement boundaries for ZBFW
- Map to physical/logical interfaces
- Types: LAN, WAN, VPN zones
- Support VLAN, L3 VPN, L2 VPN circuits
- Each zone independently secured

## Configuration Workflow

### 1. Initial Setup

**Prerequisites**
- Valid Prisma SD-WAN license (bandwidth-based or DC unlimited)
- Network design document with site topology
- IP addressing plan (management, WAN, LAN)
- Application inventory and requirements

**Activation Steps**
```
1. Access Strata Cloud Manager
2. Navigate to Activation & Onboarding
3. Claim ION devices using serial numbers
4. Assign appropriate software subscription
5. Configure basic site information
```

**Zero-Touch Provisioning (ZTP)**
- ION devices auto-register to controller on first boot
- Controller port connects to internet
- Device downloads configuration automatically
- Minimal on-site configuration required

### 2. Site Configuration

**Create Site**
```
Configuration → Prisma SD-WAN → Sites → Add Site
- Site Name, Description, Tags
- Address and Location
- Site Type: Branch or Data Center
- Admin State: Active, Monitor, or Disabled
```

**Configure Device Basic Info**
```
Configuration → Prisma SD-WAN → ION Devices → Claimed → Configure
Basic Info Tab:
- Device Name
- Deployment Mode: Analytics, Control, Disabled
- Enable L3 Direct Private WAN Forwarding (if using L3 private WAN)
- Enable L3 LAN Forwarding (for dynamic LAN routing)
```

**Note**: L3 LAN Forwarding requires no Private L2 bypass pairs configured

### 3. Interface and Circuit Configuration

**Circuit Categories**
- Define WAN circuit types: MPLS, Internet, Broadband, LTE/5G
- Used in path policies for circuit selection
- Configured globally, applied to circuits

**Configure Circuits**
```
Configuration → Prisma SD-WAN → Sites → Site → Circuits
- Circuit Name
- Category (MPLS, Internet, etc.)
- Bandwidth (Download/Upload)
- Circuit Type: Public, Private, or Private WAN
- Enable Device-Initiated Connections (for NAT traversal)
```

**Interface Configuration**
```
Configuration → Prisma SD-WAN → ION Devices → Interfaces
- Assign interface to circuit
- Configure IP addressing (Static, DHCP, PPPoE)
- VLAN tagging if required
- MTU configuration
- Enable/disable interfaces as needed
```

**Bypass Pairs (Layer 2)**
- WAN and LAN interfaces paired for failover
- Traffic bypasses ION if device fails
- Configured for private WAN underlay
- Cannot be used with L3 LAN Forwarding

**LAG/LACP Support**
- Available on ION 3200, 5200, 9200 (branch sites - 6.5+)
- Available on DC sites (6.5.2+)
- Standard 802.3ad link aggregation
- Enhanced throughput and redundancy

### 4. Routing Configuration

#### Static Routing

**Branch Static Routes**
```
Configuration → ION Devices → Device → Routing → Static Routes
- Destination Network
- Next Hop (IP or Interface)
- Scope: Local or Global
- Local: Not advertised to fabric
- Global: Advertised to other sites
```

**Use Cases**
- LAN subnets behind L3 switches
- Specific destinations via private WAN
- Standard VPN endpoint routes

#### BGP Configuration

**BGP Global Configuration**
```
Configuration → ION Devices → Device → Routing → BGP Global
- Local AS Number (1-4294967295, 4-byte ASN support)
- Router ID (IPv4 address, must be same within VRF)
- Timers: Keepalive (3-60s), Hold (9-180s)
- Maximum Paths for ECMP
```

**Create BGP Peer**
```
Configuration → ION Devices → Device → Routing → Create Peer
Peer Information:
- Name, Description, Tags
- VRF: Global or custom VRF
- Peer IP Address (IPv4/IPv6)
- Remote AS Number
- Peer Type (DC only): Core, Edge, Classic
- Router ID
- Update Source IP (multi-hop scenarios)

Route Maps:
- Route Map In: Filter incoming routes
- Route Map Out: Filter outgoing routes
- Advertise Default to Peer (optional)

Override Global Configs (optional):
- Keepalive Time
- Hold Time
- Maximum Paths
- Authentication (MD5 password)
```

**BGP Peer Types (Data Center)**
- **Core Peer**: Peers with DC core/LAN router; auto route-map generated; advertises branch prefixes
- **Edge Peer**: Peers with WAN edge/PE router; auto route-map generated; receives prefixes only
- **Classic Peer**: Manual configuration; use for complex scenarios

**Branch BGP**
- Supports classic peers only
- Peer with LAN devices, private WAN routers
- Routes exchanged with WAN and LAN peers
- Learned routes sent to controller API

**Route Advertisement Controls**
- Distribute to Fabric: Selective branch advertisement
- Host Tracking: Monitor reachability beyond peer
- Tunnel deactivation on tracking failure

#### OSPF Configuration

**OSPF Support** (Available 6.4.1+)
- Branch: LAN-side OSPF neighbors
- Data Center: LAN and WAN-side OSPF
- Full RFC compliance
- Route redistribution with BGP

**Prerequisites**
```
Enable both:
- L3 Direct Private WAN Forwarding
- L3 LAN Forwarding
Remove all Private L2 bypass pairs
```

**Configure OSPF**
```
Configuration → ION Devices → Device → Routing → OSPF

OSPF Infra Settings:
- Edit Route Maps and Prefix Lists

Create OSPF Configuration:
General Tab:
- Name
- VRF (Global or custom)
- Router ID (optional, IPv4 address)
- LAN Prefix Advertisement (Default: 0.0.0.0/0 only)
- LAN Advertisement Route Map (optional)
- Redistribute BGP (optional)
- Scope: Local or Global

Area & Interfaces Tab:
- Area ID (x.x.x.x format)
- Area Type: Standard, Stub, NSSA, Totally Stub, Totally NSSA
- Add Interfaces to area
- Interface timers:
  * Hello Interval (1-65535s, default 10)
  * Dead Interval (1-65535s, default 40)
  * Retransmit Interval (1-65535s, default 5)
  * Transit Delay (1-65535s, default 1)
- Authentication: None, Plain Text, MD5
- Network Type: Broadcast, Point-to-Point, NBMA
```

**Route Redistribution**
- BGP to OSPF: Redistribute BGP prefixes into OSPF
- OSPF to BGP: Redistribute OSPF routes into BGP
- Connected/Static to both protocols
- Configure via route maps for filtering

### 5. Policy Configuration

#### Policy Stack Architecture

**Stack Types**
- **Simple Stacks**: Single policy set, easier management
- **Advanced Stacks**: Multiple policy sets (up to 4 + default), stacked left-to-right priority

**Policy Categories**
- Path Policy: Traffic engineering, path selection
- QoS Policy: Application prioritization, DSCP marking
- Security Policy: Zone-based firewall rules
- NAT Policy: Address translation rules
- Performance Policy: SLA enforcement, FEC

#### Path Policy Configuration

**Create Path Policy Set**
```
Configuration → Prisma SD-WAN → Policies → Path → Path Stacks → Advanced

Add Path Policy Set:
- Default Rule Policy Set (includes Default + Enterprise Default)
- Create from Template
- Clone from existing Policy Set
- Blank policy set

Set Attributes:
- Name, Description, Tags
```

**Add Path Policy Rule**
```
Select Path Set → Add Rule

Info Tab:
- Name, Order (default 1024)
- Description, Tags
- Enable/Disable rule

Prefixes Tab:
- Source Prefix Filter (optional)
- Destination Prefix Filter (optional)
- Network Context (optional)

Apps Tab:
- Select Applications (up to 256 per rule)
- Filter: For sites 6.0.1+, below 6.0.1, any site
- Application types: System (PANW), System (CGX), Custom

Paths Tab:
Path Selection Method:
1. SLA Compliant Path:
   - Define SLA metrics: Latency, Loss, Jitter, MOS
   - Probe metrics: ICMP, DNS, HTTP/S
   - App metrics: TCP Init Failure, RTT, TRT (UDP)
   - Active Paths (required): SLA-compliant paths
   - Backup Paths (optional): Used if active paths non-compliant
   - L3 Failure Paths (optional): Emergency route for L3 failures

2. Best Path Selection:
   - Selects optimal path dynamically
   - No SLA constraints

Per Path Configuration:
- Overlay: Direct, Prisma SD-WAN VPN, Standard VPN
- Circuit Category: Select appropriate category
- Cannot repeat overlay + circuit category combination
```

**Path Policy Precedence** (Longest Match, Ascending Order)
1. Network Context (highest)
2. Source Prefix Filter
3. Application
4. Destination Prefix Filter (lowest)

**Path Selection Logic**
1. Apply path policy rules (longest match)
2. Filter by performance policy constraints
3. Filter by synthetic health probes
4. Filter by link quality monitoring (LQM)
5. Apply bandwidth steering
6. Select best available path

#### QoS Policy Configuration

**Create QoS Policy Set**
```
Configuration → Prisma SD-WAN → Policies → QoS → QoS Stacks → Advanced

Add QoS Policy Set:
- Default Rule Policy Set
- Create from Template
- Clone from Policy Set
- Blank policy set
```

**Add QoS Policy Rule**
```
Select QoS Set → Add Rule

Info Tab:
- Name, Order (default 1024)
- Description, Tags

Prefixes Tab:
- Network Context (highest precedence)
- Source Prefix Filter
- Destination Prefix Filter

Apps Tab:
- Select Applications (up to 256 per rule)

Priority Tab:
- Priority Class: Determines queue assignment
  * Real-Time (highest)
  * Critical
  * Important
  * Default
  * Bulk (lowest)
- Circuit Capacity Reference (for bandwidth allocation)

DSCP Tab:
- No Action: Leave DSCP unchanged
- Mark/Remark: Set DSCP value (0-63)
- Applied LAN-to-WAN direction
```

**QoS Policy Precedence** (Same as Path)
1. Network Context
2. Source Prefix Filter
3. Application
4. Destination Prefix Filter

**Circuit Capacity Configuration**
```
Configuration → Prisma SD-WAN → Policies → Circuit Capacities
- Define bandwidth allocation per priority class
- Percentage-based allocation
- Applied to QoS rules
```

#### Security Policy Configuration

**Zone-Based Firewall (ZBFW)**

**Create Security Zone**
```
Configuration → Prisma SD-WAN → Policies → Security → Security Zones

Add Security Zone:
- Name, Description, Tags
- Assign to networks/interfaces at site level
```

**Create Security Policy Stack**
```
Configuration → Prisma SD-WAN → Policies → Security → Security Stacks

Add Security Stack:
- Name, Description, Tags
- Select security policy sets (up to 4 + default)
```

**Add Security Policy Set**
```
Add Security Policy Set:
- Default Rule Policy Set (includes 3 default rules)
- Clone from existing set
- Blank policy set
```

**Add Security Policy Rule**
```
Select Security Set → Add Rule

Info Tab:
- Name, Order
- Description, Tags

Zones Tab:
- Source Zone(s)
- Destination Zone(s)

Prefixes Tab:
- Source Prefix Filter (optional)
- Destination Prefix Filter (optional)

Apps Tab:
- Select Applications

Ports Tab (optional):
- Source Ports
- Destination Ports
- Protocol

Users/Groups Tab (optional):
- User ID filtering
- Group ID filtering

Action Tab:
- Allow: Permit traffic
- Deny: Drop silently (no ICMP/RST)
- Reject: Drop with ICMP unreachable or TCP RST

Logging Tab:
- Enable/disable logging
- Syslog profile selection
```

**Default Security Rules**
1. Default Rule: Applies to internet-destined traffic
2. Enterprise Default Rule: Applies to RFC1918 traffic
3. Deny All: Explicit deny-all rule

**Security Features**
- Stateful firewall inspection
- Application-aware filtering
- Zone-based enforcement
- Supports User-ID integration
- Centralized policy management

#### Performance Policy Configuration

**Forward Error Correction (FEC)**
```
Configuration → Prisma SD-WAN → Policies → Performance

Create Performance Policy:
- Select Applications
- SLA Thresholds: Latency, Loss, Jitter
- Action: Enable FEC + Packet Duplication
- Apply when SLA violation detected
```

**Bandwidth Steering**
- Automatic path selection based on available bandwidth
- Load distribution across multiple paths
- Dynamic adaptation to congestion

#### NAT Policy Configuration

```
Configuration → Prisma SD-WAN → Policies → NAT

Add NAT Rule:
- Source/Destination prefixes
- NAT type: Source NAT, Destination NAT
- NAT pool or interface-based NAT
- Port Address Translation (PAT)
```

#### Policy Binding

**Bind to Sites**
```
Configuration → Prisma SD-WAN → Policies → Bind to Sites
- Select sites (single or multiple)
- Assign Path Stack
- Assign QoS Stack
- Assign Security Stack
- Assign NAT Stack (if applicable)
- Only one stack of each type per site
```

### 6. Application Definition

**System Applications**
- PANW-defined applications (5000+ signatures)
- Automatically updated from cloud
- Layer 7 DPI-based identification
- Includes SaaS, UC, video, enterprise apps

**Custom Applications**
```
Configuration → Prisma SD-WAN → Policies → Custom Applications

Add Custom Application:
- Name, Description, Tags
- Category
- Traffic Type
- Match Criteria:
  * IP Prefix
  * IP Protocol
  * L4 Ports (TCP/UDP)
  * DSCP values
- Bidirectional matching option
```

**System Application Overrides**
- Modify existing system app definitions
- Add custom match criteria
- Change application category
- Use when system app doesn't match traffic pattern

### 7. CloudBlades Integration

**CloudBlade Platform**
- API-based integration framework
- No firmware dependency
- Automated workflow generation
- 20+ pre-built integrations

**Common CloudBlades**

**Prisma Access Integration**
```
Configuration → Prisma SD-WAN → CloudBlades → Prisma Access

Requirements:
- Prisma Access subscription
- Prisma SD-WAN 5.2.1+
- IPSec profile configured

Configuration:
- Select Prisma Access cloud
- Service Connection or Manual Setup
- Auto-tunnel creation to nearest Prisma Access PoP
- Tag-based automation (AUTO-prisma-access)
```

**AWS Transit Gateway CloudBlade**
```
Configuration → Prisma SD-WAN → CloudBlades → AWS TGW

Features:
- Automated vION HA deployment
- Auto-connectivity to Transit Gateway
- Multi-region support
- BGP session automation
```

**Azure Virtual WAN CloudBlade**
```
Configuration → Prisma SD-WAN → CloudBlades → Azure vWAN

Features:
- Auto-configuration of secure tunnels
- Integration with Azure backbone
- Direct cloud access optimization
- Simplified vWAN hub connectivity
```

**Zscaler Integration CloudBlade**
```
Configuration → Prisma SD-WAN → CloudBlades → Zscaler

Support:
- IPSec tunnels (AUTO-zscaler tag)
- GRE tunnels (AUTO-zscaler-GRE tag - v2.0.0+)
- Automatic tunnel to Zscaler nodes
- Tag-based site enrollment

Configuration:
- Zscaler cloud selection
- Partner admin credentials
- API key configuration
- IPSec profile name
```

**Other CloudBlades**
- Google Cloud Platform
- Checkpoint
- Netskope
- ServiceNow
- Splunk
- Zoom Phone Optimization
- Megaport Virtual Edge

### 8. Monitoring and Analytics

**Dashboard Views**

**Prisma SD-WAN Summary Dashboard**
```
Navigation: Dashboard → Prisma SD-WAN Summary
- ION device connectivity status
- Link quality metrics (latency, loss, jitter, MOS)
- Top sites by alarms
- Application utilization (top 10 by bandwidth)
- Active links table
- Secure fabric tunnel status
```

**Site Summary Dashboard**
```
Navigation: Dashboard → Sites → Select Site
- Site health score
- Active/inactive circuits
- Application performance metrics
- Path selection statistics
- Security events
- Device status
```

**Predictive Analytics Dashboard**
```
Navigation: Dashboard → Predictive Analytics
- ML-based anomaly detection
- Proactive issue identification
- Site health trends
- Application health scoring
- Capacity planning insights
```

**Application Dashboard**
```
Navigation: Dashboard → Applications
- Application identification statistics
- Per-app performance metrics
- Transaction success/failure rates
- Top applications by bandwidth, sessions
- App-to-path mapping
```

**Link Quality Dashboard**
```
Navigation: Dashboard → Link Quality
- Per-link performance metrics
- Latency, loss, jitter, MOS trends
- Circuit health scoring
- Comparative link analysis
- Historical performance data
```

**Flow Browser**
```
Navigation: Analyze → Flows
- Real-time and historical flow data
- Filter by: Site, App, User, Interface, Zone
- Per-flow metrics: Bandwidth, packets, latency, loss
- Export to CSV for offline analysis
- Drill-down into specific sessions
```

### 9. Incidents and Alerts

**Alert Categories**
- **Critical**: Network down, requires immediate action
- **Warning**: Network impacted, needs attention
- **Informational**: Network degradation, attention soon

**Incident Types**
- Network: Circuit down, path failures, routing issues
- Device: Hardware failure, software issues, registration problems
- Cellular: Signal quality, carrier issues, SIM problems
- Branch HA: Failover events, sync issues
- Authentication: User-ID failures, certificate issues

**Incident Management**
```
Navigation: Incidents & Alerts → Troubleshooting

Actions:
- Acknowledge: Mark awareness, no immediate action
- Unacknowledge: Return to active incident queue
- Filter: By severity, priority, category, site, time
- Troubleshoot: Follow guided troubleshooting steps
- Go to Support: Create support ticket

Filters Available:
- Admin State: Active, Monitor, Disabled
- Severity: Critical, Warning, Informational
- Priority: P1 (highest) to P4 (lowest)
- Category: Network, Device, Cellular, Authentication
- Code: Specific event codes
- Time: Chronological sorting
- Correlation ID: Related incidents
```

**Incident Policies**
```
Configuration → Prisma SD-WAN → Policies → Incident Policies

Create Custom Thresholds:
- Latency thresholds
- Loss percentage thresholds
- Jitter thresholds
- Bandwidth utilization alerts
- Device CPU/memory thresholds
- Temperature alerts
- Custom notification rules
```

**SNMP Integration**
```
Configuration → Prisma SD-WAN → Configuration → SNMP

Configure SNMP:
- SNMP v2c or v3
- Community strings (v2c)
- Authentication/Privacy (v3)
- Trap destinations
- MIB support for monitoring platforms
```

**Syslog Integration**
```
Configuration → Prisma SD-WAN → Policies → Syslog Profiles

Configure Syslog:
- Syslog server IP/hostname
- Port (default 514)
- Protocol: UDP, TCP, TLS
- Facility codes
- Severity filtering
- Associate with security policies
```

## Operations

### Device Lifecycle Management

**Device Claiming**
```
1. Unbox ION device
2. Connect controller port to internet
3. Power on device
4. Navigate: Configuration → ION Devices → Unclaimed
5. Claim using serial number or auto-discovery
6. Assign to site
7. Apply configuration template
8. Monitor registration status
```

**Software Upgrade**
```
Configuration → ION Devices → Software Management

Process:
1. Review release notes
2. Schedule maintenance window
3. Select target version
4. Stage software to devices
5. Activate upgrade (per device or bulk)
6. Monitor upgrade progress
7. Verify post-upgrade health
8. Rollback if necessary (automatic on failure)

Best Practices:
- Upgrade controller components first
- Pilot upgrade on test/non-critical sites
- Perform upgrades during maintenance windows
- Maintain previous version for rollback
- Upgrade DC sites before branches
```

**Configuration Backup**
```
Configuration → ION Devices → Configuration Backup

Capabilities:
- Automatic daily backups
- Manual backup on-demand
- Configuration versioning
- Restore to previous configuration
- Export configuration as JSON
- Compare configuration versions
```

**RMA Process** (Enhanced in 6.5+)
```
1. Identify failed device
2. Navigate: Configuration → ION Devices → RMA
3. Select device for replacement
4. Provision replacement device
5. Ship replacement to site
6. Site personnel swap device (ZTP takeover)
7. Old device auto-deregistered
8. Return failed device
```

### Performance Optimization

**Path Selection Tuning**
- Review path selection statistics
- Adjust SLA thresholds based on actual performance
- Configure synthetic probes for critical apps
- Enable FEC for loss-sensitive applications
- Use backup paths for resilience

**QoS Optimization**
- Monitor priority queue utilization
- Adjust circuit capacity allocations
- Review DSCP marking effectiveness
- Ensure proper app classification
- Balance real-time vs bulk traffic

**Bandwidth Management**
- Monitor circuit utilization trends
- Identify top bandwidth consumers
- Apply traffic shaping where needed
- Consider circuit upgrades for consistently saturated links
- Use bandwidth steering for load distribution

**Link Quality Monitoring**
- Review LQM metrics regularly
- Identify degraded circuits
- Coordinate with ISP on poor performers
- Document baseline performance
- Track trends over time

### Security Operations

**ZBFW Policy Review**
- Audit security rules regularly
- Remove unused rules
- Review denied traffic logs
- Ensure least-privilege access
- Update rules for new applications

**User-ID Integration**
- Integrate with Active Directory
- Configure User-ID agent (if using)
- Map users to security groups
- Apply user-based policies
- Monitor user activity

**Threat Intelligence**
- Review security logs
- Identify suspicious patterns
- Coordinate with Prisma Access for advanced threats
- Update security policies based on threats
- Document security incidents

### Capacity Planning

**Monitoring Key Metrics**
- Circuit bandwidth utilization
- ION device CPU/memory usage
- Tunnel capacity
- Application growth trends
- Site expansion requirements

**Scaling Considerations**
- Device sizing for throughput requirements
- Number of tunnels per device
- BGP route scale (data centers)
- Policy complexity impacts
- Multi-tenant scaling (MSP)

## Troubleshooting

### CLI Access and Commands

**Access Methods**

**Via Web Interface**
```
1. Navigate: Configuration → ION Devices → Device
2. Select Tools → Device Toolkit
3. Opens CLI session in browser
4. Requires device credentials
```

**Via SSH** (If enabled)
```
ssh username@device-ip
Requires:
- SSH enabled on device
- User credentials configured
- Network reachability
```

**User Roles with CLI Access**
- Root
- Network Admin
- Security Admin
- Admin
- Super
- View Only (read-only)

### Essential CLI Commands

**Clear Commands** (Session/statistics clearing)
```bash
# Clear ARP cache
clear arp

# Clear BGP sessions
clear bgp [all|ipv4|ipv6]

# Clear route cache
clear routes

# Clear flow statistics
clear flows
```

**Config Commands** (Runtime configuration)
```bash
# Show running configuration
config show

# Configure static host
config static host <hostname> <ip-address>

# View interface configuration
config interface <interface-name>
```

**Debug Commands** (Active troubleshooting)
```bash
# Packet capture on interface
debug tcpdump interface <interface-name> [filter]
Example: debug tcpdump interface eth1 host 10.1.1.1

# Ping from ION device
debug ping <destination> [-c count] [-i interval]

# Traceroute
debug traceroute <destination>

# ARP interface operations
debug arping interface <interface-name> <target-ip>

# Reboot device
debug reboot [now|delayed]

# Interface debugging
debug interface <interface-name>

# Routing debugging
debug routing [bgp|ospf|static]
```

**Dump Commands** (State information)
```bash
# Interface status
dump interface [interface-name]
Example output:
Interface: eth1
Status: up
IP: 10.10.10.1/24
MAC: 00:11:22:33:44:55

# BGP peer status
dump bgp peers
Shows: Peer state, uptime, prefixes received/advertised

# Route table
dump routes [ipv4|ipv6]

# Tunnel status
dump tunnels
Shows: Tunnel state, encryption, metrics

# Service link status (Standard VPNs)
dump servicelink summary
Example output:
-------------- SERVICE LINKS ----------------------------------
Total         : 1
TotalUP       : 1
TotalDown     : 0
---------------------------------------------------------------

dump servicelink status slname=<name>
Shows: IKE/IPSec SA details, encryption, timers

dump servicelink stats slname=<name>
Shows: Rekey counts, tunnel up/down events, byte/packet counters

# Flow information
dump flows [filter options]
Example: dump flows application=Office365

# System information
dump system
Shows: CPU, memory, disk, uptime, version

# OSPF neighbors (if configured)
dump ospf neighbors

# Multicast state
dump multicast
```

**Inspect Commands** (Detailed inspection)
```bash
# Application identification status
inspect apps

# Path selection details
inspect paths

# QoS queue status
inspect qos

# Security policy hits
inspect security

# Circuit health
inspect circuits

# Detailed interface statistics
inspect interface <interface-name>
```

**SpeedTest CLI Utility** (6.3.6+)
```bash
# Run speedtest on circuit
speedtest --interface <interface-name>

# Output: Download speed, upload speed, latency
```

### Common Issues and Resolution

#### Connectivity Issues

**ION Not Registering to Controller**

**Symptoms**: Device shows offline, not appearing in Claimed Devices

**Troubleshooting Steps**:
```
1. Verify physical connectivity:
   - Check cable connections
   - Verify link lights on controller port
   
2. Check IP connectivity:
   # From CLI:
   debug ping 8.8.8.8
   debug ping controller.paloaltonetworks.com
   
3. Verify DNS resolution:
   config show | grep dns
   
4. Check NAT/Firewall:
   - Ensure outbound HTTPS (443) allowed
   - Check if PAT is working correctly
   - Verify no SSL inspection breaking connection
   
5. Review device logs:
   dump system
   # Check for certificate or time sync issues
   
6. Verify controller reachability:
   debug traceroute controller.paloaltonetworks.com
   
7. Check device claim status:
   Configuration → ION Devices → Unclaimed
   # Manually claim if auto-discovery failed
   
8. Review time synchronization:
   # Ensure NTP is working
   dump system | grep time
```

**Resolution**:
- Fix network connectivity issues
- Add firewall exceptions for Prisma SD-WAN controller
- Ensure device has valid internet access
- Verify serial number matches claimed device
- Contact support if certificate issues persist

**Tunnel Not Establishing**

**Symptoms**: Sites cannot communicate, tunnel shows down

**Troubleshooting Steps**:
```
1. Verify tunnel configuration:
   dump tunnels
   # Check tunnel state, remote endpoint
   
2. Check circuit status:
   dump interface
   # Ensure underlying interface is up
   
3. Verify IP reachability:
   debug ping <remote-site-public-ip>
   
4. Check NAT/Firewall:
   - UDP 4500 (IPSec NAT-T)
   - UDP 500 (IKE)
   - Protocol 50 (ESP)
   
5. Review IPSec parameters:
   dump servicelink status slname=<tunnel-name>
   # Check encryption, authentication, DH group mismatch
   
6. Check MTU issues:
   debug ping <remote-ip> -s 1400 -M do
   # Test with large packets
   
7. Review security policies:
   # Ensure zones allow VPN traffic
   inspect security
   
8. Check path selection:
   inspect paths
   # Verify tunnel is being selected
```

**Resolution**:
- Fix network path issues (NAT, firewall)
- Adjust MTU if fragmentation detected
- Verify IPSec profile compatibility
- Check for routing issues at remote site
- Review and correct security policies

**Poor Application Performance**

**Symptoms**: High latency, packet loss, slow application response

**Troubleshooting Steps**:
```
1. Identify affected application:
   Navigate: Analyze → Flows
   Filter by application
   
2. Check path selection:
   inspect paths
   # Verify optimal path being used
   
3. Review link quality:
   Navigation: Dashboard → Link Quality
   # Check latency, loss, jitter on active path
   
4. Verify QoS policy:
   Configuration → Policies → QoS
   # Ensure app has correct priority
   
5. Check circuit utilization:
   dump interface <interface>
   # Look for saturation
   
6. Review path policy:
   # Verify SLA thresholds appropriate
   # Check if backup path should be used
   
7. Enable FEC if lossy path:
   Configuration → Policies → Performance
   # Add performance policy with FEC
   
8. Check application identification:
   inspect apps
   # Verify app correctly identified
   
9. Analyze flow metrics:
   dump flows application=<app-name>
   # Review per-flow statistics
```

**Resolution**:
- Adjust path policy SLA thresholds
- Enable FEC for loss-sensitive apps
- Increase QoS priority for critical apps
- Add bandwidth or upgrade circuits
- Configure backup paths
- Coordinate with ISP on circuit quality

#### Routing Issues

**BGP Peer Not Establishing**

**Symptoms**: BGP peer state shows Idle, Connect, or Active

**Troubleshooting Steps**:
```
1. Verify BGP peer status:
   dump bgp peers
   
2. Check IP reachability:
   debug ping <peer-ip>
   
3. Verify BGP configuration:
   Configuration → ION Devices → Routing → Peers
   # Check peer IP, AS number, authentication
   
4. Review firewall rules:
   # Ensure TCP 179 allowed
   inspect security
   
5. Check for AS number mismatch:
   # Local AS vs Remote AS
   
6. Verify MD5 authentication:
   # If configured, ensure password matches
   
7. Review router logs:
   # Check for error messages in peer logs
   
8. Check for routing loops:
   dump routes
   # Verify no conflicting routes
```

**Resolution**:
- Correct configuration mismatches
- Fix network connectivity
- Add firewall exceptions
- Verify authentication credentials
- Check for TTL/hop-limit issues (eBGP)

**Routes Not Being Advertised**

**Symptoms**: Routes missing from BGP peer, branches cannot reach DC

**Troubleshooting Steps**:
```
1. Verify routes in table:
   dump routes
   
2. Check route map filters:
   Configuration → Routing → Route Maps
   # Review permit/deny clauses
   
3. Verify prefix lists:
   # Ensure prefixes not filtered
   
4. Check "Distribute to Fabric" setting:
   Configuration → Routing → Peers
   # For DC: Verify enabled for branch prefixes
   
5. Review scope setting:
   # Local scope won't advertise to fabric
   
6. Check BGP peer type (DC):
   # Core peers receive branch prefixes
   # Edge peers do not receive advertisements
   
7. Verify tunnel status:
   dump tunnels
   # Routes advertised only if tunnel up
   
8. Check host tracking (DC):
   # If tracking fails, routes not advertised
```

**Resolution**:
- Adjust route map filters
- Enable "Distribute to Fabric"
- Change scope to Global
- Fix tunnel connectivity
- Resolve host tracking issues
- Use correct peer type for desired behavior

**OSPF Adjacency Issues**

**Symptoms**: OSPF neighbor not forming, routes not learned

**Troubleshooting Steps**:
```
1. Verify OSPF configuration:
   Configuration → Routing → OSPF
   
2. Check OSPF neighbors:
   dump ospf neighbors
   
3. Verify interface configuration:
   dump interface
   # Ensure interface in correct area
   
4. Check hello/dead intervals:
   # Must match with peer
   
5. Verify area configuration:
   # Area ID and type must match
   
6. Check authentication:
   # If configured, must match peer
   
7. Review MTU:
   # MTU mismatch can prevent adjacency
   
8. Check network type:
   # Broadcast, P2P, NBMA must be appropriate
```

**Resolution**:
- Match timers with peer
- Correct area configuration
- Fix authentication mismatch
- Adjust MTU if needed
- Select appropriate network type

#### Policy Issues

**Traffic Not Following Expected Path**

**Symptoms**: Traffic using suboptimal path, not matching policy

**Troubleshooting Steps**:
```
1. Verify path policy configuration:
   Configuration → Policies → Path
   # Review rule order and matching criteria
   
2. Check policy binding:
   Configuration → Policies → Bind to Sites
   # Ensure correct stack assigned to site
   
3. Review application identification:
   Analyze → Flows
   # Verify app correctly identified
   
4. Check path availability:
   inspect paths
   # Verify intended path is available
   
5. Review SLA compliance:
   Dashboard → Link Quality
   # Check if SLA thresholds met
   
6. Verify network context:
   # If using, ensure correct context assigned
   
7. Check prefix filters:
   # May be overriding app-based selection
   
8. Review path selection logic:
   # Active vs Backup vs L3 Failure paths
```

**Resolution**:
- Adjust rule order (higher priority = lower order number)
- Fix application definition
- Relax SLA thresholds if too strict
- Add/modify prefix filters
- Ensure proper network context assignment
- Review and adjust path selection criteria

**Security Policy Blocking Legitimate Traffic**

**Symptoms**: Connections denied, applications failing

**Troubleshooting Steps**:
```
1. Review security logs:
   Incidents & Alerts → Filter by Security category
   
2. Check denied flows:
   Analyze → Flows
   # Filter for denied/rejected flows
   
3. Verify zone assignment:
   Configuration → Sites → Networks
   # Ensure interfaces in correct zones
   
4. Review security rules:
   Configuration → Policies → Security
   # Check rule order and matching criteria
   
5. Test with permissive rule:
   # Temporarily add allow-all rule
   # Identify where blocking occurs
   
6. Check application identification:
   # May be misidentified
   
7. Verify User-ID:
   # If using user-based policies
   
8. Review prefix filters:
   # May be incorrect source/dest filters
```

**Resolution**:
- Add explicit allow rules
- Correct zone assignments
- Fix application identification
- Adjust rule order
- Update prefix filters
- Verify User-ID integration

**QoS Not Applied Correctly**

**Symptoms**: Priority traffic experiencing delays, wrong queue assignment

**Troubleshooting Steps**:
```
1. Verify QoS policy:
   Configuration → Policies → QoS
   
2. Check policy binding:
   # Ensure QoS stack assigned to site
   
3. Review queue statistics:
   inspect qos
   
4. Verify application classification:
   Analyze → Flows
   # Check app identification
   
5. Check DSCP marking:
   # Verify DSCP values in packets
   dump flows
   
6. Review circuit capacity:
   Configuration → Policies → Circuit Capacities
   # Ensure proper allocation
   
7. Verify priority assignment:
   # Check rule matching criteria
   
8. Test with higher priority:
   # Temporarily elevate priority to confirm
```

**Resolution**:
- Correct QoS rule matching
- Adjust priority classes
- Fix DSCP marking
- Update circuit capacity allocation
- Ensure correct app identification
- Review and optimize rule order

#### Hardware and Device Issues

**High CPU/Memory Utilization**

**Symptoms**: Device slow to respond, flow processing delays

**Troubleshooting Steps**:
```
1. Check system resources:
   dump system
   
2. Review flow count:
   dump flows | count
   
3. Check tunnel count:
   dump tunnels | count
   
4. Verify software version:
   # Older versions may have known issues
   
5. Review policy complexity:
   # Too many rules can impact performance
   
6. Check for loops:
   # Routing loops or broadcast storms
   
7. Monitor over time:
   Dashboard → Device Health
   # Look for trends
```

**Resolution**:
- Upgrade to latest software version
- Simplify policies where possible
- Add more devices to distribute load
- Upgrade to higher-capacity model
- Investigate and fix routing loops
- Clear unnecessary flows/states

**Interface Flapping**

**Symptoms**: Interface going up/down repeatedly

**Troubleshooting Steps**:
```
1. Check physical layer:
   # Cable, SFP, fiber quality
   
2. Review interface logs:
   dump interface <interface-name>
   
3. Check for errors:
   inspect interface <interface-name>
   # CRC errors, frame errors
   
4. Verify duplex/speed:
   # Auto-negotiation issues
   
5. Check power budget:
   # For PoE devices
   
6. Review ISP circuit:
   # Coordinate with provider
   
7. Test with different cable:
   # Rule out cable issues
```

**Resolution**:
- Replace faulty cables/SFPs
- Hard-code speed/duplex if auto-neg failing
- Work with ISP on circuit issues
- Replace hardware if defective
- Check for EMI/environmental issues

**Device Temperature High**

**Symptoms**: Temperature alert, device slowdown or shutdown

**Troubleshooting Steps**:
```
1. Check temperature reading:
   dump system
   
2. Verify airflow:
   # Ensure vents not blocked
   
3. Check ambient temperature:
   # Room cooling adequate?
   
4. Review fan operation:
   # Fans spinning normally?
   
5. Check for dust buildup:
   # Clean if necessary
   
6. Verify rack airflow:
   # Hot aisle/cold aisle setup
```

**Resolution**:
- Improve room cooling
- Clean device vents
- Ensure proper rack spacing
- Consider ION 3200H for harsh environments
- Replace fans if faulty
- Relocate device if environmental issues

#### CloudBlade Integration Issues

**Prisma Access CloudBlade Tunnel Issues**

**Symptoms**: Tunnel to Prisma Access not establishing, traffic not flowing

**Troubleshooting Steps**:
```
1. Verify CloudBlade installation:
   Configuration → CloudBlades
   # Check status is "Installed" and "Enabled"
   
2. Check circuit tagging:
   # Ensure AUTO-prisma-access tag applied
   
3. Review tunnel status:
   dump servicelink summary
   dump servicelink status slname=<name>
   
4. Verify IPSec profile:
   Configuration → CloudBlades → Prisma Access
   # Check profile name matches
   
5. Check Prisma Access configuration:
   # Verify service connection or manual setup
   
6. Review security policies:
   # Ensure zones allow Prisma Access traffic
   
7. Check DNS resolution:
   # Prisma Access PoP reachability
   
8. Verify licensing:
   # Prisma Access license active
```

**Resolution**:
- Reinstall CloudBlade if corrupted
- Correct circuit tagging
- Fix IPSec profile mismatch
- Update Prisma Access configuration
- Add security exceptions
- Verify and renew licenses

**AWS Transit Gateway CloudBlade Issues**

**Troubleshooting Steps**:
```
1. Verify AWS credentials:
   Configuration → CloudBlades → AWS TGW
   
2. Check IAM permissions:
   # Ensure CloudBlade has required permissions
   
3. Review VPC configuration:
   # Verify VPC attachment to TGW
   
4. Check BGP sessions:
   dump bgp peers
   # Verify peering with TGW
   
5. Review route propagation:
   # AWS console: Check TGW route tables
   
6. Verify security groups:
   # Allow required traffic
   
7. Check vION health:
   # Both instances in HA pair healthy
```

**Resolution**:
- Update AWS credentials
- Fix IAM permissions
- Correct VPC/TGW configuration
- Troubleshoot BGP peering
- Update security groups
- Resolve vION HA issues

### Advanced Troubleshooting Techniques

**Packet Capture**

```bash
# Capture on specific interface
debug tcpdump interface eth1

# Capture with filter
debug tcpdump interface eth1 host 10.1.1.1

# Capture to file (limited duration)
debug tcpdump interface eth1 -w capture.pcap

# Complex filters
debug tcpdump interface eth1 "tcp port 443 and host 10.1.1.1"

# Download via web interface:
# Tools → Device Toolkit → Packet Capture → Download
```

**Flow Analysis**

```
1. Navigate: Analyze → Flows
2. Apply filters:
   - Time range
   - Site
   - Application
   - Source/Destination IP
   - Interface
3. Review metrics:
   - Bandwidth utilization
   - Packet loss
   - Latency
   - Path selected
4. Export for offline analysis
5. Correlate with incidents
```

**Log Collection**

```
1. Navigate: Configuration → ION Devices → Device
2. Select Tools → Collect Logs
3. Select log types:
   - System logs
   - Event logs
   - Debug logs
4. Download log bundle
5. Review or send to support
```

**Remote Support Access**

```
1. Navigate: Configuration → ION Devices → Device
2. Select Tools → Enable Remote Support
3. Generate support PIN
4. Provide PIN to Palo Alto Networks support
5. Support can remote troubleshoot
6. Disable when complete
```

### Performance Baselining

**Establishing Baselines**

```
1. Deploy in Analytics mode initially
2. Monitor for 2-4 weeks
3. Document:
   - Typical bandwidth usage per circuit
   - Application mix and bandwidth
   - Peak usage times
   - Link quality metrics
   - Number of flows/sessions
4. Use baseline for:
   - Capacity planning
   - SLA threshold setting
   - Anomaly detection
   - Policy optimization
```

**Key Metrics to Track**

```
Circuit Metrics:
- Bandwidth utilization (avg, 95th percentile)
- Latency (min, avg, max)
- Packet loss percentage
- Jitter
- MOS score

Application Metrics:
- Transaction success rate
- Response time
- Throughput
- Active sessions

Device Metrics:
- CPU utilization
- Memory utilization
- Flow count
- Tunnel count
- Queue drops
```

## Best Practices

### Design Best Practices

1. **Start Simple, Scale Gradually**
   - Begin with Simple policy stacks
   - Move to Advanced policies only when needed
   - Avoid over-engineering initial deployment

2. **Use Network Contexts for Segmentation**
   - Prefer network contexts over VRFs for most use cases
   - Simpler to manage and troubleshoot
   - Adequate for most segmentation needs

3. **Plan for High Availability**
   - Deploy DC IONs in HA pairs
   - Use BGP for DC HA (required)
   - Deploy virtual IONs in different availability zones
   - Implement host tracking for DC failover

4. **Leverage CloudBlades**
   - Use CloudBlades instead of manual integrations
   - Reduces configuration complexity
   - Automatic updates and maintenance
   - Request from support if not available in tenant

5. **Design for Scalability**
   - Plan for 30-50% growth in first year
   - Right-size devices for throughput needs
   - Consider management scalability (MSPs)
   - Use templates for repeatable configurations

### Operational Best Practices

1. **Policy Management**
   - Document policy intent
   - Use naming conventions consistently
   - Review policies quarterly
   - Remove unused rules
   - Test policy changes in lab/pilot

2. **Monitoring and Alerting**
   - Configure incident policies for proactive alerts
   - Set realistic thresholds (avoid alert fatigue)
   - Enable syslog for long-term retention
   - Use SNMP for integration with monitoring platforms
   - Review dashboards weekly

3. **Change Management**
   - Schedule changes during maintenance windows
   - Test in non-production first
   - Document rollback procedures
   - Notify stakeholders
   - Monitor post-change for issues

4. **Software Management**
   - Stay current with software releases (within 2-3 releases)
   - Review release notes thoroughly
   - Pilot on non-critical sites first
   - Maintain previous version for rollback
   - Coordinate DC and branch upgrades

5. **Security Hygiene**
   - Regularly audit ZBFW policies
   - Implement least-privilege access
   - Monitor security logs
   - Keep application signatures updated
   - Integrate with Prisma Access for advanced security

6. **Documentation**
   - Maintain network diagrams
   - Document custom applications
   - Keep runbooks updated
   - Document security zones and policies
   - Track configuration changes

### Troubleshooting Best Practices

1. **Methodical Approach**
   - Define the problem clearly
   - Gather relevant information
   - Form hypothesis
   - Test systematically
   - Document findings

2. **Use Built-in Tools First**
   - Check dashboards before CLI
   - Review incidents and alerts
   - Use flow browser for traffic analysis
   - Leverage predictive analytics
   - CLI when detailed troubleshooting needed

3. **Engage Support Effectively**
   - Collect logs before contacting support
   - Provide clear problem description
   - Document troubleshooting steps taken
   - Enable remote support access
   - Follow up on recommendations

4. **Knowledge Building**
   - Participate in Palo Alto Networks community
   - Review best practices documentation
   - Take training courses
   - Lab test before production changes
   - Share knowledge within team

## Reference Information

### Port Requirements

**ION to Controller**
- TCP 443 (HTTPS): Management and control
- NTP (UDP 123): Time synchronization
- DNS (UDP 53): Name resolution

**ION to ION (Prisma SD-WAN VPN)**
- UDP 4500: IPSec NAT-T (primary)
- UDP 500: IKE (negotiation)
- IP Protocol 50: ESP (alternative if no NAT)

**Standard VPN**
- UDP 4500: IPSec NAT-T
- UDP 500: IKE
- GRE (IP Protocol 47): If using GRE tunnels

**Management Access**
- SSH: TCP 22 (if enabled)
- SNMP: UDP 161 (queries), UDP 162 (traps)
- Syslog: UDP 514 or TCP 514 or TCP 6514 (TLS)

### Capacity Limits

**Per Device**
- Maximum tunnels: Varies by model (1000-5000+)
- Maximum flows: Varies by model (100K-1M+)
- Maximum routes: 1M+ (DC models)
- Maximum BGP peers: 100+ (DC models)
- Maximum policy rules: 1000s

**Per Tenant**
- Maximum sites: 10,000+
- Maximum devices: 10,000+
- Maximum policies: 1000s per type

### Software Versions

**Current Releases** (as of knowledge cutoff)
- Latest: 6.5.x series
- Previous: 6.4.x series
- Minimum supported: 6.1.x+ (check compatibility matrix)

**Upgrade Path**
- Can skip intermediate versions in most cases
- Review release notes for specific path requirements
- Controller upgraded automatically (SaaS)
- ION devices upgraded by administrator

### Supported Routing Protocols

**Dynamic Routing**
- BGP4 with 4-byte ASN support
- OSPF v2 (IPv4)
- Multicast: PIM Sparse Mode

**Static Routing**
- IPv4 and IPv6 static routes
- Interface-based or next-hop based
- Scope: Local or Global

**Route Redistribution**
- BGP ↔ OSPF
- BGP ↔ Static
- OSPF ↔ Static
- Connected routes into any protocol

### Application Identification

**Methods**
- Layer 7 DPI (primary)
- IP/Port patterns
- DSCP marking
- SSL/TLS fingerprinting
- Behavioral analysis

**Application Database**
- 5000+ pre-defined applications
- Cloud-updated signatures
- Custom application support
- Application overrides available

### API and Automation

**REST API**
- Full configuration API
- Status and statistics retrieval
- Event and alert API
- CloudBlade SDK

**Python SDK**
- Prisma SD-WAN Python SDK available
- Simplifies automation tasks
- Examples and documentation provided

**Terraform Provider**
- Infrastructure-as-code support
- Manage sites, devices, policies
- Version control friendly

### Support Resources

**Documentation**
- https://docs.paloaltonetworks.com/prisma-sd-wan
- Hardware reference guides
- Deployment guides
- Integration guides

**Community**
- https://live.paloaltonetworks.com/
- Best practices articles
- Discussion forums
- User groups

**Training**
- EDU-238: Prisma SD-WAN Design and Operation
- Online learning portal
- Partner training programs

**Support**
- https://support.paloaltonetworks.com
- Case management
- Knowledge base
- Software downloads

## Glossary

- **AppFabric**: Prisma SD-WAN's application-defined network fabric
- **CloudBlade**: API-based integration platform for third-party services
- **ION**: Instant-On Network device (Prisma SD-WAN appliance)
- **LQM**: Link Quality Monitoring
- **SASE**: Secure Access Service Edge
- **ZBFW**: Zone-Based Firewall
- **ZTP**: Zero-Touch Provisioning
- **vION**: Virtual ION (software appliance)
- **Network Context**: Traffic segmentation construct
- **Path Stack**: Collection of path policy sets
- **QoS Stack**: Collection of QoS policy sets
- **Security Stack**: Collection of security policy sets
- **SLA**: Service Level Agreement
- **FEC**: Forward Error Correction
- **DPI**: Deep Packet Inspection
- **MOS**: Mean Opinion Score (VoIP quality metric)

---

## Usage Notes

This skill should be referenced when:
- Designing new Prisma SD-WAN deployments
- Configuring sites, devices, and policies
- Integrating with cloud services (Prisma Access, AWS, Azure)
- Troubleshooting connectivity, performance, or policy issues
- Optimizing existing Prisma SD-WAN environments
- Planning upgrades or expansions
- Implementing security policies
- Configuring dynamic routing (BGP, OSPF)

Always consult official Palo Alto Networks documentation for the most current information, as features and capabilities evolve with each software release.