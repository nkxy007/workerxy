---
name: network-troubleshooting
description: Systematic methodology for diagnosing and resolving TCP/IP network connectivity issues, including physical layer problems, routing issues, DNS failures, application-layer problems, and performance degradation. Use when troubleshooting network outages, connectivity failures, slow performance, or any IP networking issues.
license: Apache-2.0
metadata:
  author: network-troubleshooting-skill
  version: "1.0"
  based_on: "Cisco Internetworking Troubleshooting Handbook"
---

# Network Troubleshooting Skill

## Overview

This skill provides a comprehensive, structured approach to troubleshooting TCP/IP network connectivity issues based on industry best practices and Cisco's proven methodologies. It covers troubleshooting from Layer 1 (Physical) through Layer 7 (Application) of the OSI model.

## When to Use This Skill

Use this skill when:
- Users report network connectivity problems
- Applications cannot reach servers or services
- Network performance is degraded
- Routing or switching issues are suspected
- DNS resolution is failing
- Need to diagnose firewall or ACL blocking
- Troubleshooting VPN or WAN connectivity
- Investigating intermittent network problems

## Troubleshooting Methodology

### Core Principles

1. **Follow a Structured Approach**: Use systematic methods (top-down, bottom-up, divide-and-conquer, or follow-the-path)
2. **Document Everything**: Record symptoms, tests performed, results, and changes made
3. **Start Simple**: Check basics first (cables, power, configuration) before complex issues
4. **One Change at a Time**: Make incremental changes and test after each
5. **Gather Information First**: Understand the problem fully before attempting fixes

### The 8-Step Troubleshooting Process

1. **Define the Problem**
   - Identify symptoms clearly
   - Determine scope (single user, department, network-wide)
   - Gather timeline information (when did it start, what changed)
   
2. **Gather Detailed Information**
   - Interview affected users
   - Review system logs and alerts
   - Check monitoring systems
   - Review recent configuration changes
   
3. **Consider Probable Causes**
   - Develop theories based on symptoms
   - Consider OSI layer most likely affected
   - Review common issues for the symptom type
   
4. **Devise a Plan**
   - Determine testing approach
   - Identify tools needed
   - Plan rollback if changes fail
   
5. **Implement the Plan**
   - Execute tests systematically
   - Make changes carefully
   - Document each step
   
6. **Observe Results**
   - Verify if issue is resolved
   - Check for side effects
   - Test thoroughly
   
7. **Iterate if Necessary**
   - If unresolved, return to step 3
   - Refine theory based on new data
   
8. **Document and Report**
   - Record final solution
   - Update network documentation
   - Create knowledge base entry

## Essential Troubleshooting Tools

### Command-Line Tools

#### ping
Tests basic IP connectivity using ICMP echo request/reply.

**Usage:**
```bash
ping <ip_address>
ping -c 5 <ip_address>  # Linux: send 5 packets
ping -n 5 <ip_address>  # Windows: send 5 packets
ping -s 1500 <ip_address>  # Test with larger packet size (MTU testing)
```

**Interpreting Results:**
- `!` (success): Packet reached destination and returned
- `.` (timeout): No response received
- `U` (unreachable): ICMP unreachable received
- `C` (congestion): Source quench received
- High RTT variance: Network congestion or routing issues

#### traceroute/tracert
Shows the path packets take through the network.

**Usage:**
```bash
traceroute <destination>  # Linux/Mac
tracert <destination>     # Windows
```

**Interpreting Results:**
- `* * *`: Hop not responding (may be firewall/ACL blocking)
- Latency spikes: Identify where delays occur
- Routing loops: Same hop appearing multiple times
- Path changes: Multiple paths to destination

#### nslookup/dig
Tests DNS name resolution.

**Usage:**
```bash
nslookup <hostname>
nslookup <hostname> <dns_server>
dig <hostname>
dig @<dns_server> <hostname>
```

#### netstat/ss
Shows network connections and listening ports.

**Usage:**
```bash
netstat -an  # All connections and listening ports
netstat -rn  # Routing table
ss -tuln     # Linux: TCP/UDP listening ports
```

#### tcpdump/Wireshark
Capture and analyze network packets.

**Usage:**
```bash
tcpdump -i eth0 -n host 10.1.1.1
tcpdump -i eth0 port 80 -w capture.pcap
```

### Network Device Commands (Cisco)

```
show ip interface brief      # Interface status and IP addresses
show interfaces             # Detailed interface statistics
show ip route               # Routing table
show ip arp                 # ARP cache
show running-config         # Current configuration
show version                # System information
show processes cpu          # CPU utilization
show memory                 # Memory usage
show ip access-lists        # Access control lists
show ip nat translations    # NAT translations
```

## Troubleshooting Approaches

### 1. Top-Down Approach
Start at Layer 7 (Application) and work down to Layer 1 (Physical).

**Best for:**
- Application-specific issues
- User can ping but cannot access service
- Protocol-specific problems

**Example:**
```
User cannot access web server but can ping it:
1. Check browser (Layer 7)
2. Verify HTTP/HTTPS service running (Layer 7)
3. Check TCP connection (Layer 4)
4. Verify routing (Layer 3)
```

### 2. Bottom-Up Approach
Start at Layer 1 (Physical) and work up to Layer 7 (Application).

**Best for:**
- Complete connectivity loss
- Hardware-related issues
- Legacy equipment problems

**Example:**
```
No network connectivity:
1. Check cable connection (Layer 1)
2. Verify link lights (Layer 1)
3. Check switch port status (Layer 2)
4. Verify IP configuration (Layer 3)
5. Test routing (Layer 3)
```

### 3. Divide-and-Conquer Approach
Start in the middle (usually Layer 3/4) and move up or down based on results.

**Best for:**
- Unknown root cause
- Most efficient for experienced troubleshooters
- Complex multi-layer issues

**Example:**
```
Unknown connectivity issue:
1. Start with ping test (Layer 3)
2. If ping fails → move down to Layer 2/1
3. If ping succeeds → move up to Layer 4/7
```

### 4. Follow-the-Path Approach
Trace the traffic flow from source to destination.

**Best for:**
- Routing issues
- Complex network topologies
- Identifying where packets are dropped

**Example:**
```
Use traceroute to identify path
Test connectivity at each hop
Verify configuration on devices in path
```

## Common Problem Categories

### Physical Layer (Layer 1) Issues

**Symptoms:**
- No link light on interface
- Interface shows "down/down"
- High error rates on interface

**Troubleshooting Steps:**
1. Verify cable is connected properly
2. Check for physical damage to cable
3. Test with known-good cable
4. Verify correct cable type (straight-through vs crossover)
5. Check transceiver is seated properly
6. Test different port if available
7. Verify speed/duplex settings match

**Common Causes:**
- Damaged or unplugged cables
- Wrong cable type
- Faulty network interface card (NIC)
- Bad transceiver
- Port disabled on switch

### Data Link Layer (Layer 2) Issues

**Symptoms:**
- Interface up but no connectivity
- MAC address not in ARP table
- VLAN mismatch errors

**Troubleshooting Steps:**
1. Check switch port configuration
2. Verify VLAN assignment
3. Check spanning tree status
4. Review MAC address table
5. Verify duplex settings match on both ends
6. Check for broadcast storms

**Common Causes:**
- VLAN misconfiguration
- Spanning tree blocking port
- Duplex mismatch
- MAC address conflicts

### Network Layer (Layer 3) Issues

**Symptoms:**
- Can ping local subnet but not remote networks
- Routing table missing routes
- TTL exceeded errors

**Troubleshooting Steps:**
1. Verify IP address and subnet mask configuration
2. Check default gateway is correct and reachable
3. Review routing table for destination route
4. Verify routing protocol operation
5. Check for routing loops
6. Test with extended ping specifying source interface
7. Verify ip classless is configured (if using default route)

**Common Causes:**
- Incorrect IP configuration
- Missing or incorrect routes
- Routing protocol issues
- Routing loops
- ACL blocking traffic

### Transport Layer (Layer 4) Issues

**Symptoms:**
- Connection timeouts
- Connections reset unexpectedly
- Application cannot establish connection

**Troubleshooting Steps:**
1. Verify service is listening on correct port
2. Check firewall rules allow traffic
3. Test with telnet to service port
4. Review TCP connection states
5. Check for port number conflicts

**Common Causes:**
- Firewall blocking ports
- Service not running
- Port conflicts
- ACL blocking protocol

### Application Layer (Layer 7) Issues

**Symptoms:**
- Specific application fails while others work
- Authentication failures
- Protocol-specific errors

**Troubleshooting Steps:**
1. Verify service is running
2. Check application logs
3. Test authentication separately
4. Verify protocol version compatibility
5. Check for application-specific firewall rules
6. Review NAT configuration for embedded IP addresses

**Common Causes:**
- Service not running or misconfigured
- Authentication issues
- Version incompatibilities
- NAT breaking application protocols (FTP, SIP)

## Specific Scenarios

### DNS Resolution Failure

**Symptoms:**
- Cannot access sites by name but IP addresses work
- nslookup fails

**Troubleshooting:**
```bash
# Verify DNS server configured
ipconfig /all           # Windows
cat /etc/resolv.conf    # Linux

# Test DNS resolution
nslookup www.google.com
nslookup www.google.com 8.8.8.8

# Test ping to DNS server
ping <dns_server_ip>

# Check if DNS service is running (on DNS server)
# Verify DNS records exist for the domain
```

### Intermittent Connectivity

**Symptoms:**
- Works sometimes, fails other times
- Packet loss in ping tests

**Troubleshooting:**
1. Check for duplicate IP addresses
2. Review interface statistics for errors
3. Monitor CPU and memory usage on devices
4. Check for routing protocol flapping
5. Look for intermittent cable/port issues
6. Check for network congestion
7. Review for spanning tree changes

### Cannot Reach Specific Website/Server

**Symptoms:**
- One service/server unreachable
- Other services work fine

**Troubleshooting:**
```bash
# Test basic connectivity
ping <server_ip>
traceroute <server_ip>

# Test DNS
nslookup <server_name>

# Test specific port
telnet <server_ip> <port>
nc -zv <server_ip> <port>

# Check for ACLs blocking
# Verify NAT/PAT configuration
# Check firewall rules
```

### Network Performance Issues

**Symptoms:**
- Slow application response
- High latency
- Packet loss

**Troubleshooting:**
1. Baseline current performance (ping, throughput tests)
2. Check interface utilization
3. Review QoS configuration
4. Check for errors/drops on interfaces
5. Monitor switch/router CPU and memory
6. Check for broadcast storms
7. Review routing protocol metrics
8. Test for MTU issues

## Advanced Diagnostics

### Packet Capture Analysis

**When to Use:**
- Application-specific issues
- Need to see exact traffic flow
- Troubleshooting NAT/firewall issues

**Best Practices:**
- Apply capture filters to limit data
- Capture at multiple points (client, server, intermediary)
- Analyze for retransmissions, duplicate ACKs
- Look for TCP window issues

### Debug Commands (Use with Caution)

**Cisco Debug:**
```
# WARNING: Debug commands can severely impact router performance
# Only use with access list to limit output

configure terminal
access-list 101 permit ip host 10.1.1.1 host 10.2.2.2
end

debug ip packet 101 detail

# To stop debugging
undebug all
```

**Prerequisites:**
- Physical access to device
- Low CPU utilization (<30%)
- Console logging disabled
- Buffered logging enabled

### Resource Checking

**Router/Switch Resources:**
```
show processes cpu
show processes memory
show buffers
show interfaces | include queue
```

**Signs of Resource Issues:**
- CPU >90% sustained
- Memory free <10%
- Input/output queue drops
- Buffer allocation failures

## Application-Specific Troubleshooting

### HTTP/HTTPS
```bash
# Test HTTP connectivity
telnet <server> 80
curl -v http://<server>

# Test HTTPS
openssl s_client -connect <server>:443

# Check certificate
openssl s_client -connect <server>:443 -showcerts
```

### FTP
- Check both control (21) and data connection
- Try passive mode if active fails
- Verify firewall allows FTP data connections
- Check for NAT issues with PORT command

### Email (SMTP/POP/IMAP)
```bash
# Test SMTP
telnet <mail_server> 25

# Test POP3
telnet <mail_server> 110

# Test IMAP
telnet <mail_server> 143
```

### SSH/Telnet
- Verify service listening on correct port
- Check for DNS reverse lookup delays
- Verify authentication method supported
- Check for TCP wrapper restrictions

## Documentation Template

After resolving issues, document using this template:

```
Issue: [Brief description]
Date/Time: [When reported and resolved]
Affected: [Users, systems, services impacted]
Symptoms: [What users experienced]
Root Cause: [Actual cause identified]
Troubleshooting Steps:
  1. [Step 1 taken]
  2. [Step 2 taken]
  ...
Resolution: [What fixed the issue]
Prevention: [How to prevent recurrence]
Lessons Learned: [What was learned]
```

## Best Practices

1. **Always Document**
   - Record all tests performed
   - Note all configuration changes
   - Save before/after configurations
   - Create timeline of events

2. **Verify Before Assuming**
   - Don't assume configurations are correct
   - Test rather than trust status displays
   - Verify both directions of traffic flow

3. **Isolate Variables**
   - Change one thing at a time
   - Test after each change
   - Have rollback plan ready

4. **Use Baselines**
   - Know normal performance metrics
   - Compare current state to baseline
   - Document network topology

5. **Consider Security**
   - Check ACLs and firewall rules early
   - Verify security policies aren't blocking
   - Don't disable security to troubleshoot

6. **Escalate Appropriately**
   - Know when to escalate
   - Document what was tried
   - Provide clear handoff information

## Common Mistakes to Avoid

1. **Not gathering enough information before starting**
2. **Making multiple changes simultaneously**
3. **Assuming the problem is what the user says it is**
4. **Not testing the fix thoroughly**
5. **Forgetting to document the solution**
6. **Not following up to verify long-term fix**
7. **Using debug commands in production without safeguards**
8. **Not having a rollback plan**

## Quick Reference Checklists

### Basic Connectivity Checklist
- [ ] Verify physical connections (cables, LEDs)
- [ ] Check IP configuration (address, mask, gateway)
- [ ] Ping default gateway
- [ ] Ping remote host by IP
- [ ] Ping remote host by name (DNS test)
- [ ] Traceroute to destination
- [ ] Check routing table
- [ ] Verify no ACLs blocking

### Performance Issue Checklist
- [ ] Baseline current performance
- [ ] Check interface statistics for errors
- [ ] Monitor CPU/memory on network devices
- [ ] Check for broadcast storms
- [ ] Verify no duplex mismatches
- [ ] Review QoS configuration
- [ ] Test for MTU issues
- [ ] Check application server performance

### Routing Issue Checklist
- [ ] Verify routing table has route to destination
- [ ] Check routing protocol status
- [ ] Verify metric/administrative distance
- [ ] Test with extended ping from multiple interfaces
- [ ] Check for routing loops
- [ ] Verify route redistribution if applicable
- [ ] Check for route filtering

## Additional Resources

For detailed protocol-specific information, refer to:
- `references/TCP-IP-PROTOCOLS.md` - Detailed TCP/IP protocol information
- `references/COMMON-ISSUES.md` - Database of common issues and solutions
- `references/VENDOR-SPECIFIC.md` - Vendor-specific commands and procedures
- `scripts/network-test.sh` - Automated network testing script

## When to Escalate

Escalate to senior network engineers or vendors when:
- Issue appears to be hardware failure
- Problem persists after exhausting known solutions
- Issue requires access/permissions you don't have
- Software bug is suspected
- Vendor support is needed for proprietary equipment
- Security incident is suspected
- Issue impacts business-critical systems