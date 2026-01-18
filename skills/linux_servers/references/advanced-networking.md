# Advanced Networking Reference

## Layer 1 & 2 Advanced Scenarios

### NIC Offloading Optimization

Modern NICs support various offload features to reduce CPU overhead:

```bash
# Check current offload settings
sudo ethtool -k eth0

# Commonly tuned offloads:
# TSO (TCP Segmentation Offload) - splits large TCP packets
sudo ethtool -K eth0 tso on

# GSO (Generic Segmentation Offload)
sudo ethtool -K eth0 gso on

# GRO (Generic Receive Offload) - merges received packets
sudo ethtool -K eth0 gro on

# LRO (Large Receive Offload)
sudo ethtool -K eth0 lro on

# RX/TX checksumming
sudo ethtool -K eth0 rx on tx on

# Scatter-gather
sudo ethtool -K eth0 sg on

# When to disable offloads:
# - Network monitoring/packet capture (tcpdump accuracy)
# - Certain VPN configurations
# - Troubleshooting packet issues
# - Container networking issues
```

### Multi-Queue NIC Configuration

```bash
# Check number of queues
ethtool -l eth0

# Set number of combined queues
sudo ethtool -L eth0 combined 4

# Check IRQ affinity
cat /proc/interrupts | grep eth0

# Set IRQ affinity (bind to specific CPU cores)
echo 1 > /proc/irq/125/smp_affinity  # Core 0
echo 2 > /proc/irq/126/smp_affinity  # Core 1
echo 4 > /proc/irq/127/smp_affinity  # Core 2

# Use irqbalance for automatic distribution
sudo systemctl start irqbalance
```

### SR-IOV (Single Root I/O Virtualization)

```bash
# Check if NIC supports SR-IOV
lspci -vvv | grep -i sriov

# Enable SR-IOV
echo 4 > /sys/class/net/eth0/device/sriov_numvfs

# List virtual functions
lspci | grep Virtual

# Assign VF to VM (with libvirt)
virsh attach-interface --domain vm1 --type hostdev --source 0000:05:10.0
```

### VLAN Trunking and Native VLAN

```bash
# Create trunk port with multiple VLANs
sudo ip link add link eth0 name eth0.10 type vlan id 10
sudo ip link add link eth0 name eth0.20 type vlan id 20
sudo ip link add link eth0 name eth0.30 type vlan id 30

# Bring up all VLANs
for vlan in 10 20 30; do
    sudo ip link set eth0.$vlan up
done

# Native VLAN (untagged traffic)
# Configure eth0 directly for native VLAN, sub-interfaces for tagged
sudo ip addr add 192.168.1.1/24 dev eth0  # Native VLAN
sudo ip addr add 192.168.10.1/24 dev eth0.10  # VLAN 10
```

### QinQ (802.1ad) - VLAN Stacking

```bash
# Outer VLAN (S-VLAN)
sudo ip link add link eth0 name eth0.100 type vlan proto 802.1ad id 100

# Inner VLAN (C-VLAN)
sudo ip link add link eth0.100 name eth0.100.200 type vlan proto 802.1Q id 200

# Configure and bring up
sudo ip addr add 10.0.0.1/24 dev eth0.100.200
sudo ip link set eth0.100 up
sudo ip link set eth0.100.200 up
```

### Bridge with VLAN Filtering

```bash
# Create bridge with VLAN awareness
sudo ip link add name br0 type bridge vlan_filtering 1

# Add ports
sudo ip link set eth0 master br0
sudo ip link set eth1 master br0

# Configure VLANs on bridge ports
bridge vlan add vid 10 dev eth0
bridge vlan add vid 20 dev eth0
bridge vlan add vid 10 dev eth1

# Set PVID (Port VLAN ID - untagged traffic)
bridge vlan add vid 10 pvid untagged dev eth0

# Show VLAN filtering
bridge vlan show
```

### Advanced Bonding Scenarios

**LACP Troubleshooting:**
```bash
# Check LACP status
cat /proc/net/bonding/bond0 | grep -A 5 "802.3ad"

# Verify partner (switch) LACP
cat /proc/net/bonding/bond0 | grep "Partner Mac Address"

# Common LACP issues:
# 1. Mismatched LACP rates (slow vs fast)
# 2. Switch not configured for LACP
# 3. Mismatched bonding modes
# 4. MTU mismatch between bond members
```

**Active-Backup with Primary:**
```bash
# Create active-backup bond
sudo ip link add bond0 type bond mode active-backup

# Set primary interface
sudo ip link set bond0 type bond primary eth0

# Set fail_over_mac
sudo ip link set bond0 type bond fail_over_mac 1
```

**Bond monitoring:**
```bash
# Monitor bond changes
watch -n 1 cat /proc/net/bonding/bond0

# Bond state via sysfs
cat /sys/class/net/bond0/bonding/mode
cat /sys/class/net/bond0/bonding/slaves
cat /sys/class/net/bond0/bonding/active_slave
```

## Layer 3 Advanced Scenarios

### Multiple Default Gateways with Metrics

```bash
# Add default routes with different metrics
sudo ip route add default via 192.168.1.1 metric 100
sudo ip route add default via 192.168.2.1 metric 200

# Lower metric = higher priority
# Second route used if first fails
```

### Source-Based Routing for Multi-WAN

```bash
# Scenario: Two ISPs, route traffic based on source

# Create routing tables in /etc/iproute2/rt_tables
echo "100 isp1" | sudo tee -a /etc/iproute2/rt_tables
echo "200 isp2" | sudo tee -a /etc/iproute2/rt_tables

# Add routes to tables
sudo ip route add default via 10.0.1.1 dev eth0 table isp1
sudo ip route add default via 10.0.2.1 dev eth1 table isp2

# Add rules for source routing
sudo ip rule add from 10.0.1.0/24 table isp1
sudo ip rule add from 10.0.2.0/24 table isp2

# Add local network routes to both tables
sudo ip route add 192.168.1.0/24 dev br0 table isp1
sudo ip route add 192.168.1.0/24 dev br0 table isp2

# Load balancing with multipath
sudo ip route add default scope global nexthop via 10.0.1.1 dev eth0 weight 1 \
                                     nexthop via 10.0.2.1 dev eth1 weight 1
```

### VRF (Virtual Routing and Forwarding)

```bash
# Create VRF
sudo ip link add vrf-blue type vrf table 10
sudo ip link set vrf-blue up

# Assign interface to VRF
sudo ip link set eth1 master vrf-blue

# Add route in VRF context
sudo ip route add default via 192.168.1.1 table 10

# Run command in VRF context
sudo ip vrf exec vrf-blue ping 8.8.8.8

# List VRFs
ip vrf show

# Show routes in specific VRF
ip route show vrf vrf-blue
```

### VXLAN (Virtual Extensible LAN)

```bash
# Create VXLAN interface
sudo ip link add vxlan10 type vxlan \
    id 10 \
    remote 192.168.1.20 \
    local 192.168.1.10 \
    dev eth0 \
    dstport 4789

# Add to bridge
sudo ip link add br0 type bridge
sudo ip link set vxlan10 master br0
sudo ip link set vxlan10 up
sudo ip link set br0 up

# Multicast VXLAN
sudo ip link add vxlan10 type vxlan \
    id 10 \
    group 239.1.1.1 \
    dev eth0 \
    dstport 4789

# Show VXLAN info
ip -d link show vxlan10
```

### IP-IP and GRE Tunnels with IPsec

```bash
# GRE over IPsec scenario
# 1. Create GRE tunnel
sudo ip tunnel add gre1 mode gre remote 203.0.113.2 local 203.0.113.1
sudo ip addr add 10.0.0.1/30 dev gre1
sudo ip link set gre1 up

# 2. Install strongSwan for IPsec
sudo apt install strongswan -y

# 3. Configure IPsec (/etc/ipsec.conf)
# conn gre-tunnel
#     left=203.0.113.1
#     right=203.0.113.2
#     authby=secret
#     type=transport
#     esp=aes256-sha256
#     auto=start

# 4. Add PSK (/etc/ipsec.secrets)
# 203.0.113.1 203.0.113.2 : PSK "your-secret-key"
```

### IPv6 Transition Mechanisms

**6to4 Tunnel:**
```bash
# Automatic IPv6 over IPv4
sudo ip tunnel add tun6to4 mode sit remote any local 203.0.113.1
sudo ip link set tun6to4 up
sudo ip addr add 2002:cb00:7101::1/64 dev tun6to4
sudo ip route add 2000::/3 via ::192.88.99.1 dev tun6to4
```

**Dual Stack:**
```bash
# Enable both IPv4 and IPv6
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 192.168.1.10/24
        - 2001:db8::10/64
      gateway4: 192.168.1.1
      gateway6: 2001:db8::1
      nameservers:
        addresses:
          - 8.8.8.8
          - 2001:4860:4860::8888
```

## Layer 4 Advanced Scenarios

### TCP Window Scaling and Optimization

```bash
# High-bandwidth, high-latency networks (satellite, long distance)
sudo sysctl -w net.ipv4.tcp_window_scaling=1
sudo sysctl -w net.ipv4.tcp_timestamps=1
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 134217728"
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 134217728"

# Calculate optimal buffer size:
# Buffer = Bandwidth (bits/sec) * RTT (sec) / 8
# Example: 100Mbps * 0.1s / 8 = 1.25MB
```

### TCP Congestion Control Algorithms

```bash
# Available algorithms
sysctl net.ipv4.tcp_available_congestion_control

# Set congestion control
sudo sysctl -w net.ipv4.tcp_congestion_control=bbr

# BBR (Bottleneck Bandwidth and RTT)
# - Best for high-bandwidth, lossy networks
# - Default in modern kernels

# CUBIC (default in older kernels)
# - Good general purpose

# Reno (classic)
# - Conservative, good for stable networks

# Test different algorithms
iperf3 -c server -C bbr
```

### Connection Tracking Optimization

```bash
# Increase conntrack table size
sudo sysctl -w net.netfilter.nf_conntrack_max=262144

# Adjust timeouts
sudo sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=432000
sudo sysctl -w net.netfilter.nf_conntrack_tcp_timeout_time_wait=30

# Check current connections
cat /proc/sys/net/netfilter/nf_conntrack_count
cat /proc/sys/net/netfilter/nf_conntrack_max

# View conntrack entries
sudo conntrack -L | wc -l
```

### Advanced Traffic Shaping with tc

**Hierarchical Token Bucket (HTB) Setup:**
```bash
# Scenario: 100Mbit total, allocate to different services

# Root qdisc
sudo tc qdisc add dev eth0 root handle 1: htb default 30

# Root class
sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 100mbit

# HTTP class - 50Mbit guaranteed, can burst to 80Mbit
sudo tc class add dev eth0 parent 1:1 classid 1:10 htb rate 50mbit ceil 80mbit prio 1

# SSH class - 10Mbit guaranteed, can burst to 20Mbit
sudo tc class add dev eth0 parent 1:1 classid 1:20 htb rate 10mbit ceil 20mbit prio 0

# Other traffic - 20Mbit guaranteed
sudo tc class add dev eth0 parent 1:1 classid 1:30 htb rate 20mbit ceil 100mbit prio 2

# Add SFQ to prevent single flow from dominating
sudo tc qdisc add dev eth0 parent 1:10 handle 10: sfq perturb 10
sudo tc qdisc add dev eth0 parent 1:20 handle 20: sfq perturb 10
sudo tc qdisc add dev eth0 parent 1:30 handle 30: sfq perturb 10

# Filters to classify traffic
sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 \
    match ip dport 80 0xffff flowid 1:10
sudo tc filter add dev eth0 protocol ip parent 1:0 prio 0 u32 \
    match ip dport 22 0xffff flowid 1:20

# Monitor
tc -s class show dev eth0
```

**Priority Queueing (PRIO):**
```bash
# Three priority bands
sudo tc qdisc add dev eth0 root handle 1: prio bands 3

# Classify by TOS/DSCP
sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 \
    match ip tos 0x10 0xff flowid 1:1  # Low delay (SSH, VoIP)
sudo tc filter add dev eth0 protocol ip parent 1:0 prio 2 u32 \
    match ip tos 0x08 0xff flowid 1:2  # High throughput
```

### Socket Options and TCP Tuning

```bash
# Disable Nagle's algorithm (low latency)
sudo sysctl -w net.ipv4.tcp_nodelay=1

# Enable TCP Fast Open
sudo sysctl -w net.ipv4.tcp_fastopen=3

# SYN cookies (protection against SYN flood)
sudo sysctl -w net.ipv4.tcp_syncookies=1

# Increase SYN backlog
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=8192

# TCP keepalive
sudo sysctl -w net.ipv4.tcp_keepalive_time=600
sudo sysctl -w net.ipv4.tcp_keepalive_intvl=60
sudo sysctl -w net.ipv4.tcp_keepalive_probes=3

# TIME_WAIT recycling (use carefully)
sudo sysctl -w net.ipv4.tcp_tw_reuse=1

# Increase local port range
sudo sysctl -w net.ipv4.ip_local_port_range="10000 65535"
```

## Network Troubleshooting Tools

### Advanced tcpdump Filters

```bash
# Capture only SYN packets
sudo tcpdump -i eth0 'tcp[tcpflags] & (tcp-syn) != 0'

# Capture packets with specific TTL
sudo tcpdump -i eth0 'ip[8] < 5'

# Capture fragmented packets
sudo tcpdump -i eth0 'ip[6:2] & 0x1fff != 0'

# Capture packets with specific TCP flags
sudo tcpdump -i eth0 'tcp[13] = 2'  # SYN
sudo tcpdump -i eth0 'tcp[13] = 18' # SYN-ACK

# Capture by packet size
sudo tcpdump -i eth0 'greater 1000'
sudo tcpdump -i eth0 'less 64'

# Capture broadcast/multicast
sudo tcpdump -i eth0 broadcast
sudo tcpdump -i eth0 multicast

# Save with rotation
sudo tcpdump -i eth0 -w capture.pcap -C 100 -W 10
# -C 100: 100MB files
# -W 10: Keep 10 files
```

### Network Performance Testing

**iperf3 Advanced:**
```bash
# UDP bandwidth test
iperf3 -c server -u -b 100M

# Parallel streams
iperf3 -c server -P 4

# Reverse test (server sends)
iperf3 -c server -R

# Bidirectional test
iperf3 -c server --bidir

# Test with specific MSS
iperf3 -c server -M 1400

# JSON output
iperf3 -c server -J > results.json
```

**nuttcp:**
```bash
# Install
sudo apt install nuttcp -y

# Server mode
nuttcp -S

# Client test
nuttcp -t server_ip
nuttcp -r server_ip  # Receive test

# UDP test
nuttcp -u -t server_ip
```

**netperf:**
```bash
# Install
sudo apt install netperf -y

# TCP_STREAM test
netperf -H server_ip

# UDP_STREAM
netperf -H server_ip -t UDP_STREAM

# Request/Response (latency)
netperf -H server_ip -t TCP_RR
```

### MTU Path Discovery

```bash
# Find optimal MTU
ping -M do -s 1472 -c 4 8.8.8.8
# If successful, MTU = 1472 + 28 (IP+ICMP headers) = 1500

# Test different sizes
for size in 1400 1450 1472 1500; do
    echo "Testing MTU $((size + 28))"
    ping -M do -s $size -c 1 8.8.8.8 && echo "Success" || echo "Too large"
done

# Set MTU
sudo ip link set dev eth0 mtu 1400

# Persistent (Netplan)
network:
  version: 2
  ethernets:
    eth0:
      mtu: 1400
```

### Network Namespace Isolation Testing

```bash
# Create test environment
sudo ip netns add test1
sudo ip netns add test2

# Create veth pairs
sudo ip link add veth0 type veth peer name veth1
sudo ip link add veth2 type veth peer name veth3

# Assign to namespaces
sudo ip link set veth1 netns test1
sudo ip link set veth3 netns test2

# Configure
sudo ip netns exec test1 ip addr add 10.0.0.1/24 dev veth1
sudo ip netns exec test1 ip link set veth1 up
sudo ip netns exec test2 ip addr add 10.0.0.2/24 dev veth3
sudo ip netns exec test2 ip link set veth3 up

# Bridge them
sudo ip link add br0 type bridge
sudo ip link set veth0 master br0
sudo ip link set veth2 master br0
sudo ip link set br0 up
sudo ip link set veth0 up
sudo ip link set veth2 up

# Test connectivity
sudo ip netns exec test1 ping -c 3 10.0.0.2
```

## Security and Filtering

### DDoS Mitigation with iptables

```bash
# Limit new connections per IP
sudo iptables -A INPUT -p tcp --dport 80 -m connlimit --connlimit-above 20 -j DROP

# Rate limit ICMP
sudo iptables -A INPUT -p icmp -m limit --limit 1/s --limit-burst 5 -j ACCEPT
sudo iptables -A INPUT -p icmp -j DROP

# Protect against SYN flood
sudo iptables -N syn_flood
sudo iptables -A INPUT -p tcp --syn -j syn_flood
sudo iptables -A syn_flood -m limit --limit 1/s --limit-burst 3 -j RETURN
sudo iptables -A syn_flood -j DROP

# Block invalid packets
sudo iptables -A INPUT -m state --state INVALID -j DROP

# Log and drop port scans
sudo iptables -A INPUT -p tcp --tcp-flags ALL NONE -j LOG --log-prefix "NULL scan: "
sudo iptables -A INPUT -p tcp --tcp-flags ALL NONE -j DROP
sudo iptables -A INPUT -p tcp --tcp-flags ALL ALL -j LOG --log-prefix "XMAS scan: "
sudo iptables -A INPUT -p tcp --tcp-flags ALL ALL -j DROP
```

### GeoIP Blocking

```bash
# Install xtables-addons
sudo apt install xtables-addons-common -y

# Download GeoIP database
sudo mkdir -p /usr/share/xt_geoip
cd /tmp
wget https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).csv.gz
gunzip dbip-country-lite-$(date +%Y-%m).csv.gz

# Convert to xtables format
sudo /usr/lib/xtables-addons/xt_geoip_build -D /usr/share/xt_geoip dbip-country-lite-$(date +%Y-%m).csv

# Block country (e.g., CN - China)
sudo iptables -A INPUT -m geoip --src-cc CN -j DROP

# Allow only specific countries
sudo iptables -A INPUT -m geoip --src-cc US,CA,GB -j ACCEPT
sudo iptables -A INPUT -j DROP
```

This reference provides deep-dive scenarios for production network engineering and troubleshooting.