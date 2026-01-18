---
name: linux-server-mgmt
description: Specialized Linux server administration for Ubuntu and RedHat-based systems (RHEL, CentOS, Rocky, AlmaLinux). Use when managing, configuring, troubleshooting, or securing Linux servers including system monitoring, package management, service configuration, user administration, network setup (basic and advanced Layer 1-4 networking with ethtool, VLANs, bonding, bridging, advanced routing, traffic control, iptables/nftables), security hardening, log analysis, performance tuning, backup/restore operations, and automation tasks.
---

# Linux Server Management

Comprehensive administration toolkit for Ubuntu and RedHat-based Linux servers with battle-tested commands, workflows, and best practices.

## Quick Reference

### Distribution Detection

Always detect the distribution before running distribution-specific commands:

```bash
# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
    VERSION=$VERSION_ID
fi

# Check package manager
if command -v apt &> /dev/null; then
    PKG_MGR="apt"
elif command -v dnf &> /dev/null; then
    PKG_MGR="dnf"
elif command -v yum &> /dev/null; then
    PKG_MGR="yum"
fi
```

## Core Administration Tasks

### Package Management

**Ubuntu (APT):**
```bash
# Update package lists
sudo apt update

# Upgrade packages
sudo apt upgrade -y

# Full upgrade (handle dependencies)
sudo apt full-upgrade -y

# Install package
sudo apt install <package> -y

# Remove package (keep config)
sudo apt remove <package>

# Purge package (remove config)
sudo apt purge <package>

# Search for package
apt search <keyword>

# Show package info
apt show <package>

# List installed packages
apt list --installed

# Clean package cache
sudo apt clean
sudo apt autoclean
sudo apt autoremove
```

**RedHat (DNF/YUM):**
```bash
# Update package lists
sudo dnf check-update  # or yum check-update

# Upgrade packages
sudo dnf upgrade -y    # or yum update -y

# Install package
sudo dnf install <package> -y

# Remove package
sudo dnf remove <package>

# Search for package
dnf search <keyword>

# Show package info
dnf info <package>

# List installed packages
dnf list installed

# Clean cache
sudo dnf clean all

# List enabled repositories
dnf repolist
```

### Service Management (systemd)

```bash
# Start/stop/restart service
sudo systemctl start <service>
sudo systemctl stop <service>
sudo systemctl restart <service>

# Enable/disable service at boot
sudo systemctl enable <service>
sudo systemctl disable <service>

# Check service status
sudo systemctl status <service>

# View service logs
sudo journalctl -u <service> -f

# List all services
systemctl list-units --type=service

# List failed services
systemctl --failed

# Reload systemd daemon
sudo systemctl daemon-reload
```

### User & Group Management

```bash
# Add user
sudo useradd -m -s /bin/bash <username>
sudo passwd <username>

# Add user with home directory and specific UID
sudo useradd -m -u 1500 -s /bin/bash <username>

# Delete user
sudo userdel <username>
sudo userdel -r <username>  # Also remove home directory

# Modify user
sudo usermod -aG <group> <username>  # Add to group
sudo usermod -s /bin/bash <username>  # Change shell

# Lock/unlock user
sudo usermod -L <username>  # Lock
sudo usermod -U <username>  # Unlock

# Create group
sudo groupadd <groupname>

# Delete group
sudo groupdel <groupname>

# List user's groups
groups <username>

# View user info
id <username>
finger <username>
```

### File Permissions & Ownership

```bash
# Change ownership
sudo chown user:group <file>
sudo chown -R user:group <directory>

# Change permissions
chmod 755 <file>
chmod -R 644 <directory>

# Special permissions
chmod u+s <file>  # SUID
chmod g+s <file>  # SGID
chmod +t <dir>    # Sticky bit

# Set default ACLs
setfacl -d -m u::rwx,g::rx,o::rx <directory>

# View ACLs
getfacl <file>
```

### Disk & Filesystem Management

```bash
# Check disk usage
df -h
du -sh /path/to/directory
du -sh * | sort -h

# Check inode usage
df -i

# Mount/unmount
sudo mount /dev/sdb1 /mnt/data
sudo umount /mnt/data

# View mounts
mount | column -t
findmnt

# Create filesystem
sudo mkfs.ext4 /dev/sdb1
sudo mkfs.xfs /dev/sdb1

# Check filesystem
sudo fsck /dev/sdb1
sudo xfs_repair /dev/sdb1

# LVM operations
sudo pvcreate /dev/sdb
sudo vgcreate vg_data /dev/sdb
sudo lvcreate -L 10G -n lv_data vg_data
sudo lvextend -L +5G /dev/vg_data/lv_data
sudo resize2fs /dev/vg_data/lv_data  # ext4
sudo xfs_growfs /mount/point         # xfs

# /etc/fstab entry examples
# UUID=xxx /mnt/data ext4 defaults 0 2
# /dev/mapper/vg_data-lv_data /data xfs defaults 0 0
```

### Network Configuration

**Ubuntu (Netplan):**
```bash
# Configuration file: /etc/netplan/*.yaml
# Example:
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: false
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]

# Apply netplan config
sudo netplan apply

# Test configuration
sudo netplan try
```

**RedHat (NetworkManager):**
```bash
# Configuration files: /etc/sysconfig/network-scripts/ifcfg-*

# Using nmcli
nmcli device status
nmcli connection show
nmcli connection up <connection>
nmcli connection down <connection>

# Add static IP
sudo nmcli con mod eth0 ipv4.addresses 192.168.1.100/24
sudo nmcli con mod eth0 ipv4.gateway 192.168.1.1
sudo nmcli con mod eth0 ipv4.dns "8.8.8.8 8.8.4.4"
sudo nmcli con mod eth0 ipv4.method manual
sudo nmcli con up eth0

# Restart networking
sudo systemctl restart NetworkManager
```

**Common network commands:**
```bash
# Show IP addresses
ip addr show
ip -4 addr
ip -6 addr

# Show routing table
ip route show

# Test connectivity
ping -c 4 <host>
traceroute <host>
mtr <host>

# DNS lookup
dig <domain>
nslookup <domain>
host <domain>

# Port scanning
ss -tulpn
netstat -tulpn
lsof -i :<port>

# Firewall status
sudo iptables -L -n -v
sudo firewall-cmd --list-all  # RedHat
sudo ufw status              # Ubuntu
```

### Advanced Network Configuration

#### Layer 1 - Physical Layer Tools

**ethtool - NIC configuration and diagnostics:**
```bash
# Install ethtool
sudo apt install ethtool -y  # Ubuntu
sudo dnf install ethtool -y  # RedHat

# Show interface information
sudo ethtool eth0

# Show driver information
sudo ethtool -i eth0

# Show statistics
sudo ethtool -S eth0

# Check link status
sudo ethtool eth0 | grep "Link detected"

# Show ring buffer settings
sudo ethtool -g eth0

# Show offload settings
sudo ethtool -k eth0

# Set speed and duplex (force 1000Mbps full duplex)
sudo ethtool -s eth0 speed 1000 duplex full autoneg off

# Enable/disable specific offload
sudo ethtool -K eth0 tx off
sudo ethtool -K eth0 gso off
sudo ethtool -K eth0 tso off

# Wake-on-LAN configuration
sudo ethtool -s eth0 wol g  # Enable WoL
sudo ethtool eth0 | grep Wake-on

# Show/modify ring buffer size
sudo ethtool -G eth0 rx 4096 tx 4096

# Show/modify interrupt coalescing
sudo ethtool -c eth0
sudo ethtool -C eth0 rx-usecs 50

# Test cable/PHY (generates traffic)
sudo ethtool -t eth0
```

**mii-tool - Media Independent Interface (older alternative):**
```bash
# Show link status
mii-tool eth0

# Force speed/duplex
sudo mii-tool -F 100baseTx-FD eth0
```

#### Layer 2 - Data Link Layer

**ARP Management:**
```bash
# Show ARP cache
ip neigh show
arp -n

# Add static ARP entry
sudo ip neigh add 192.168.1.10 lladdr 00:11:22:33:44:55 dev eth0

# Delete ARP entry
sudo ip neigh del 192.168.1.10 dev eth0

# Flush ARP cache
sudo ip neigh flush all

# Send gratuitous ARP
arping -c 3 -I eth0 192.168.1.10
```

**VLAN Configuration:**
```bash
# Install vlan package
sudo apt install vlan -y  # Ubuntu
sudo dnf install vconfig -y  # RedHat (or use ip command)

# Load 8021q module
sudo modprobe 8021q
echo "8021q" | sudo tee -a /etc/modules

# Create VLAN interface
sudo ip link add link eth0 name eth0.100 type vlan id 100

# Assign IP to VLAN
sudo ip addr add 192.168.100.1/24 dev eth0.100
sudo ip link set dev eth0.100 up

# Show VLAN interfaces
ip -d link show type vlan

# Delete VLAN interface
sudo ip link delete eth0.100

# Netplan VLAN configuration (Ubuntu):
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: false
  vlans:
    vlan100:
      id: 100
      link: eth0
      addresses: [192.168.100.1/24]
```

**Bridge Configuration (Layer 2 switching):**
```bash
# Install bridge-utils
sudo apt install bridge-utils -y  # Ubuntu
sudo dnf install bridge-utils -y  # RedHat

# Create bridge
sudo ip link add name br0 type bridge

# Add interfaces to bridge
sudo ip link set eth0 master br0
sudo ip link set eth1 master br0

# Configure bridge IP
sudo ip addr add 192.168.1.1/24 dev br0

# Bring up bridge and interfaces
sudo ip link set eth0 up
sudo ip link set eth1 up
sudo ip link set br0 up

# Show bridge information
bridge link show
brctl show

# Enable STP (Spanning Tree Protocol)
sudo ip link set br0 type bridge stp_state 1

# Show bridge STP info
bridge -d link show

# Remove interface from bridge
sudo ip link set eth0 nomaster

# Delete bridge
sudo ip link delete br0

# Netplan bridge configuration (Ubuntu):
network:
  version: 2
  bridges:
    br0:
      interfaces: [eth0, eth1]
      addresses: [192.168.1.1/24]
      parameters:
        stp: true
        forward-delay: 15
```

**Bonding/Teaming (Link Aggregation):**
```bash
# Install bonding
sudo modprobe bonding
echo "bonding" | sudo tee -a /etc/modules

# Create bond interface
sudo ip link add bond0 type bond mode 802.3ad

# Set bond parameters
sudo ip link set bond0 type bond miimon 100
sudo ip link set bond0 type bond lacp_rate fast

# Add slaves to bond
sudo ip link set eth0 master bond0
sudo ip link set eth1 master bond0

# Configure IP
sudo ip addr add 192.168.1.1/24 dev bond0
sudo ip link set bond0 up

# Show bonding info
cat /proc/net/bonding/bond0

# Bonding modes:
# 0 - balance-rr (round robin)
# 1 - active-backup
# 2 - balance-xor
# 3 - broadcast
# 4 - 802.3ad (LACP)
# 5 - balance-tlb
# 6 - balance-alb

# Netplan bonding configuration (Ubuntu):
network:
  version: 2
  bonds:
    bond0:
      interfaces: [eth0, eth1]
      addresses: [192.168.1.1/24]
      parameters:
        mode: 802.3ad
        lacp-rate: fast
        mii-monitor-interval: 100

# nmcli bonding (RedHat):
sudo nmcli con add type bond ifname bond0 mode 802.3ad
sudo nmcli con add type ethernet ifname eth0 master bond0
sudo nmcli con add type ethernet ifname eth1 master bond0
sudo nmcli con mod bond0 ipv4.addresses 192.168.1.1/24
sudo nmcli con mod bond0 ipv4.method manual
sudo nmcli con up bond0
```

**MAC Address Management:**
```bash
# Show MAC address
ip link show eth0 | grep link/ether

# Change MAC address (temporary)
sudo ip link set dev eth0 down
sudo ip link set dev eth0 address 00:11:22:33:44:55
sudo ip link set dev eth0 up

# Make permanent in Netplan (Ubuntu):
network:
  version: 2
  ethernets:
    eth0:
      macaddress: 00:11:22:33:44:55
      addresses: [192.168.1.10/24]

# Make permanent with nmcli (RedHat):
sudo nmcli con mod eth0 ethernet.cloned-mac-address 00:11:22:33:44:55
```

#### Layer 3 - Network Layer

**Advanced Routing:**
```bash
# Add static route
sudo ip route add 10.0.0.0/8 via 192.168.1.254 dev eth0

# Add default gateway
sudo ip route add default via 192.168.1.1

# Delete route
sudo ip route del 10.0.0.0/8

# Show routing table
ip route show
ip route show table all

# Show specific route
ip route get 8.8.8.8

# Multiple routing tables
# Edit /etc/iproute2/rt_tables
# Add: 100 custom_table

# Add route to specific table
sudo ip route add 10.0.0.0/8 via 192.168.1.254 table 100

# Add rule to use specific table
sudo ip rule add from 192.168.1.0/24 table 100

# Show rules
ip rule show

# Show specific routing table
ip route show table 100

# Flush routing table
sudo ip route flush table 100
```

**Policy-Based Routing:**
```bash
# Route based on source IP
sudo ip rule add from 192.168.1.0/24 table 100 priority 100

# Route based on destination
sudo ip rule add to 10.0.0.0/8 table 100

# Route based on interface
sudo ip rule add iif eth0 table 100

# Route based on fwmark (firewall mark)
sudo ip rule add fwmark 1 table 100

# Delete rule
sudo ip rule del from 192.168.1.0/24 table 100
```

**IP Tunneling:**
```bash
# GRE Tunnel
sudo ip tunnel add gre1 mode gre remote 203.0.113.2 local 203.0.113.1 ttl 255
sudo ip addr add 10.0.0.1/30 dev gre1
sudo ip link set gre1 up

# IPIP Tunnel
sudo ip tunnel add ipip1 mode ipip remote 203.0.113.2 local 203.0.113.1
sudo ip addr add 10.0.0.1/30 dev ipip1
sudo ip link set ipip1 up

# Delete tunnel
sudo ip tunnel del gre1

# Show tunnels
ip tunnel show
```

**Network Namespaces:**
```bash
# Create namespace
sudo ip netns add blue

# List namespaces
ip netns list

# Run command in namespace
sudo ip netns exec blue bash

# Create veth pair (virtual ethernet)
sudo ip link add veth0 type veth peer name veth1

# Move interface to namespace
sudo ip link set veth1 netns blue

# Configure interface in namespace
sudo ip netns exec blue ip addr add 10.0.0.1/24 dev veth1
sudo ip netns exec blue ip link set veth1 up

# Delete namespace
sudo ip netns del blue
```

**IPv6 Configuration:**
```bash
# Show IPv6 addresses
ip -6 addr show

# Add IPv6 address
sudo ip -6 addr add 2001:db8::1/64 dev eth0

# Show IPv6 routing table
ip -6 route show

# Add IPv6 route
sudo ip -6 route add 2001:db8:1::/64 via 2001:db8::254

# Enable/disable IPv6
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=0  # Enable
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1  # Disable

# IPv6 neighbor discovery (like ARP)
ip -6 neigh show

# Test IPv6 connectivity
ping6 2001:4860:4860::8888
traceroute6 google.com
```

#### Layer 4 - Transport Layer

**TCP/UDP Socket Analysis:**
```bash
# Show all sockets
ss -a

# Show listening sockets
ss -l

# Show TCP sockets
ss -t
ss -ta  # All TCP
ss -tl  # Listening TCP

# Show UDP sockets
ss -u
ss -ua  # All UDP
ss -ul  # Listening UDP

# Show process using socket
ss -tp
ss -tlnp  # Listening TCP with process and port numbers

# Show socket statistics
ss -s

# Show specific port
ss -tlnp | grep :80

# Show sockets for specific state
ss state established
ss state time-wait
ss state syn-sent

# Filter by address
ss dst 192.168.1.10
ss src 192.168.1.0/24

# Extended socket information
ss -e
ss -m  # Memory information
ss -i  # Internal TCP information
```

**netstat (legacy but still useful):**
```bash
# Show all connections
netstat -a

# Show listening ports
netstat -l

# Show with process ID
netstat -p

# Numeric addresses (no DNS resolution)
netstat -n

# Continuous monitoring
netstat -c

# Show routing table
netstat -r

# Show interface statistics
netstat -i

# Protocol statistics
netstat -s
```

**Traffic Control (tc) - QoS and Bandwidth Management:**
```bash
# Show current qdiscs (queuing disciplines)
tc qdisc show

# Add rate limiting (Token Bucket Filter)
sudo tc qdisc add dev eth0 root tbf rate 1mbit burst 32kbit latency 400ms

# Delete qdisc
sudo tc qdisc del dev eth0 root

# HTB (Hierarchical Token Bucket) - more control
sudo tc qdisc add dev eth0 root handle 1: htb default 30

# Add class with bandwidth limit
sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 100mbit
sudo tc class add dev eth0 parent 1:1 classid 1:10 htb rate 50mbit ceil 100mbit
sudo tc class add dev eth0 parent 1:1 classid 1:20 htb rate 30mbit ceil 100mbit

# Add filter to classify traffic
sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 \
  match ip dst 192.168.1.10/32 flowid 1:10

# Show class details
tc -s class show dev eth0

# Network emulation (delay, packet loss, etc.)
sudo tc qdisc add dev eth0 root netem delay 100ms
sudo tc qdisc add dev eth0 root netem loss 1%
sudo tc qdisc add dev eth0 root netem delay 100ms 10ms  # +/- 10ms variance

# Combined: delay + loss + reordering
sudo tc qdisc add dev eth0 root netem delay 100ms 10ms loss 1% reorder 25% 50%

# Bandwidth limiting with wondershaper
sudo apt install wondershaper -y
sudo wondershaper -a eth0 -d 1024 -u 512  # Download 1Mbit, Upload 512Kbit
sudo wondershaper -c -a eth0  # Clear
```

**Connection Tracking (conntrack):**
```bash
# Install conntrack
sudo apt install conntrack -y  # Ubuntu
sudo dnf install conntrack-tools -y  # RedHat

# Show all connections
sudo conntrack -L

# Show by protocol
sudo conntrack -L -p tcp
sudo conntrack -L -p udp

# Show connection count
sudo conntrack -C

# Show statistics
sudo conntrack -S

# Delete connection
sudo conntrack -D -p tcp --orig-port-dst 80

# Flush connection table
sudo conntrack -F
```

**iptables - Advanced Packet Filtering:**
```bash
# NAT (Network Address Translation)
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Port forwarding (DNAT)
sudo iptables -t nat -A PREROUTING -p tcp --dport 8080 -j DNAT --to-destination 192.168.1.10:80

# SNAT (Source NAT)
sudo iptables -t nat -A POSTROUTING -o eth0 -j SNAT --to-source 203.0.113.1

# Mangle table (modify packets)
sudo iptables -t mangle -A PREROUTING -p tcp --dport 80 -j MARK --set-mark 1

# Show NAT table
sudo iptables -t nat -L -n -v

# Show mangle table
sudo iptables -t mangle -L -n -v

# Connection tracking states
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Rate limiting
sudo iptables -A INPUT -p tcp --dport 22 -m limit --limit 3/min -j ACCEPT

# Recent module (track IPs)
sudo iptables -A INPUT -p tcp --dport 22 -m recent --set --name SSH
sudo iptables -A INPUT -p tcp --dport 22 -m recent --update --seconds 60 --hitcount 4 --name SSH -j DROP
```

**nftables (modern replacement for iptables):**
```bash
# Install nftables
sudo apt install nftables -y  # Ubuntu
sudo dnf install nftables -y  # RedHat

# List current ruleset
sudo nft list ruleset

# Create table
sudo nft add table inet filter

# Create chain
sudo nft add chain inet filter input { type filter hook input priority 0 \; }

# Add rule
sudo nft add rule inet filter input tcp dport 22 accept

# Add NAT rule
sudo nft add table nat
sudo nft add chain nat postrouting { type nat hook postrouting priority 100 \; }
sudo nft add rule nat postrouting masquerade

# Save rules
sudo nft list ruleset > /etc/nftables.conf

# Flush rules
sudo nft flush ruleset
```

**Advanced Network Diagnostics:**
```bash
# tcpdump - packet capture
sudo tcpdump -i eth0
sudo tcpdump -i eth0 port 80
sudo tcpdump -i eth0 host 192.168.1.10
sudo tcpdump -i eth0 -w capture.pcap  # Write to file
sudo tcpdump -i eth0 -c 100  # Capture 100 packets

# tshark (Wireshark CLI)
sudo apt install tshark -y
sudo tshark -i eth0
sudo tshark -i eth0 -f "port 80"

# ngrep - network grep
sudo apt install ngrep -y
sudo ngrep -d eth0 'HTTP' port 80

# iftop - bandwidth by connection
sudo apt install iftop -y
sudo iftop -i eth0

# nethogs - bandwidth by process
sudo apt install nethogs -y
sudo nethogs eth0

# iperf3 - network performance testing
sudo apt install iperf3 -y
# Server:
iperf3 -s
# Client:
iperf3 -c server_ip

# nload - network load visualization
sudo apt install nload -y
nload eth0

# bmon - bandwidth monitor
sudo apt install bmon -y
bmon
```

**Network Performance Tuning:**
```bash
# TCP tuning in /etc/sysctl.conf or /etc/sysctl.d/
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.core.rmem_default = 65536
net.core.wmem_default = 65536
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq
net.ipv4.tcp_mtu_probing = 1

# Apply changes
sudo sysctl -p

# TCP BBR congestion control
echo "tcp_bbr" | sudo tee -a /etc/modules-load.d/modules.conf
sudo modprobe tcp_bbr
```

### Firewall Management

**Ubuntu (UFW):**
```bash
# Enable/disable
sudo ufw enable
sudo ufw disable

# Allow/deny rules
sudo ufw allow 22/tcp
sudo ufw allow from 192.168.1.0/24 to any port 22
sudo ufw deny 80/tcp

# Delete rule
sudo ufw delete allow 80/tcp

# Status
sudo ufw status verbose
sudo ufw status numbered

# Reset firewall
sudo ufw reset
```

**RedHat (firewalld):**
```bash
# Enable/disable
sudo systemctl enable --now firewalld
sudo systemctl stop firewalld

# Add/remove services
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --remove-service=http
sudo firewall-cmd --reload

# Add/remove ports
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --permanent --remove-port=8080/tcp
sudo firewall-cmd --reload

# List rules
sudo firewall-cmd --list-all
sudo firewall-cmd --list-services
sudo firewall-cmd --list-ports

# Zones
sudo firewall-cmd --get-active-zones
sudo firewall-cmd --zone=public --list-all
```

### System Monitoring

```bash
# CPU and memory
top
htop
vmstat 1
mpstat -P ALL 1

# Memory details
free -h
cat /proc/meminfo

# Disk I/O
iostat -x 1
iotop

# Network traffic
iftop
nethogs
nload

# Process monitoring
ps aux
ps -ef
pstree
pgrep <process>

# System load
uptime
w

# Logged in users
who
last
lastlog
```

### Log Analysis

```bash
# System logs
sudo journalctl -xe
sudo journalctl -u <service>
sudo journalctl --since "1 hour ago"
sudo journalctl -f

# Traditional logs (if rsyslog installed)
sudo tail -f /var/log/syslog      # Ubuntu
sudo tail -f /var/log/messages    # RedHat
sudo tail -f /var/log/auth.log    # Ubuntu
sudo tail -f /var/log/secure      # RedHat

# Apache/Nginx logs
sudo tail -f /var/log/apache2/error.log  # Ubuntu
sudo tail -f /var/log/httpd/error_log    # RedHat
sudo tail -f /var/log/nginx/error.log

# Search logs
sudo grep -i "error" /var/log/syslog
sudo journalctl | grep -i "failed"

# Log rotation
logrotate -d /etc/logrotate.conf  # Debug mode
```

### Security Hardening

**SSH Hardening:**
```bash
# Edit /etc/ssh/sshd_config
sudo vim /etc/ssh/sshd_config

# Recommended settings:
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
Protocol 2

# Restart SSH
sudo systemctl restart sshd
```

**Automatic Updates:**

Ubuntu:
```bash
# Install unattended-upgrades
sudo apt install unattended-upgrades -y

# Configure
sudo dpkg-reconfigure -plow unattended-upgrades

# Edit /etc/apt/apt.conf.d/50unattended-upgrades
```

RedHat:
```bash
# Install dnf-automatic
sudo dnf install dnf-automatic -y

# Configure /etc/dnf/automatic.conf
apply_updates = yes

# Enable service
sudo systemctl enable --now dnf-automatic.timer
```

**SELinux (RedHat):**
```bash
# Check status
sestatus
getenforce

# Set mode
sudo setenforce 0  # Permissive
sudo setenforce 1  # Enforcing

# Make permanent in /etc/selinux/config
SELINUX=enforcing

# Troubleshooting
sudo ausearch -m avc -ts recent
sudo audit2why < /var/log/audit/audit.log
sudo audit2allow -a
```

**AppArmor (Ubuntu):**
```bash
# Status
sudo aa-status

# Modes
sudo aa-enforce /etc/apparmor.d/<profile>
sudo aa-complain /etc/apparmor.d/<profile>
sudo aa-disable /etc/apparmor.d/<profile>

# Reload profiles
sudo systemctl reload apparmor
```

### Performance Tuning

**Kernel Parameters:**
```bash
# View current settings
sysctl -a
sysctl vm.swappiness

# Temporary change
sudo sysctl -w vm.swappiness=10

# Permanent change in /etc/sysctl.conf or /etc/sysctl.d/*.conf
vm.swappiness=10
net.core.rmem_max=134217728
net.core.wmem_max=134217728

# Apply changes
sudo sysctl -p
```

**Swap Management:**
```bash
# View swap
swapon --show
free -h

# Create swap file
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent in /etc/fstab
/swapfile none swap sw 0 0

# Remove swap
sudo swapoff /swapfile
sudo rm /swapfile
```

### Backup & Restore

**Using tar:**
```bash
# Backup
sudo tar -czf backup-$(date +%Y%m%d).tar.gz /path/to/data

# Restore
sudo tar -xzf backup.tar.gz -C /restore/location

# Incremental backup
sudo tar -czf backup.tar.gz --listed-incremental=snapshot.file /data
```

**Using rsync:**
```bash
# Local backup
sudo rsync -avz --delete /source/ /backup/

# Remote backup
sudo rsync -avz -e ssh /source/ user@remote:/backup/

# Exclude patterns
sudo rsync -avz --exclude='*.log' --exclude='cache/' /source/ /backup/
```

**System backup (full):**
```bash
# Backup entire system (excluding virtual filesystems)
sudo tar -czpf /backup/system-$(date +%Y%m%d).tar.gz \
  --exclude=/backup \
  --exclude=/proc \
  --exclude=/sys \
  --exclude=/dev \
  --exclude=/run \
  --exclude=/tmp \
  --exclude=/mnt \
  --exclude=/media \
  /
```

### Cron Jobs & Scheduling

```bash
# Edit user crontab
crontab -e

# Edit root crontab
sudo crontab -e

# List crontabs
crontab -l
sudo crontab -l

# Cron format: minute hour day month weekday command
# Examples:
0 2 * * * /path/to/backup.sh           # Daily at 2 AM
*/15 * * * * /path/to/monitor.sh       # Every 15 minutes
0 0 * * 0 /path/to/weekly.sh           # Weekly on Sunday
0 3 1 * * /path/to/monthly.sh          # Monthly on 1st at 3 AM

# System-wide cron directories
/etc/cron.daily/
/etc/cron.weekly/
/etc/cron.monthly/

# Using systemd timers (alternative to cron)
sudo systemctl list-timers
```

## Troubleshooting Workflows

### System Won't Boot

1. Boot into recovery/rescue mode
2. Check recent changes: `sudo journalctl -xb -1`
3. Verify filesystem: `sudo fsck -y /dev/sda1`
4. Check fstab: `cat /etc/fstab`
5. Review boot logs: `dmesg | less`
6. Check GRUB configuration: `/etc/default/grub`

### High CPU Usage

1. Identify process: `top` or `htop`
2. Details: `ps aux | grep <PID>`
3. Thread view: `top -H -p <PID>`
4. Check logs: `sudo journalctl -u <service>`
5. Strace process: `sudo strace -p <PID>`

### High Memory Usage

1. Check usage: `free -h`
2. Top consumers: `ps aux --sort=-%mem | head`
3. Details per process: `pmap <PID>`
4. Check for memory leaks: `valgrind <command>`
5. Review swap usage: `vmstat 1`

### Disk Full

1. Check usage: `df -h`
2. Find large files: `sudo du -h / | sort -h | tail -20`
3. Find large directories: `sudo du -sh /* | sort -h`
4. Clean package cache: `sudo apt clean` or `sudo dnf clean all`
5. Clean logs: `sudo journalctl --vacuum-size=100M`
6. Find old files: `find /var/log -type f -mtime +30`

### Network Issues

1. Check interface: `ip addr show`
2. Check routing: `ip route show`
3. Test connectivity: `ping -c 4 8.8.8.8`
4. DNS test: `dig google.com`
5. Check firewall: `sudo iptables -L -n` or `sudo ufw status`
6. Review network logs: `sudo journalctl -u NetworkManager`

### Service Won't Start

1. Check status: `sudo systemctl status <service>`
2. View logs: `sudo journalctl -u <service> -n 50`
3. Check config syntax: Depends on service (e.g., `nginx -t`)
4. Verify permissions: `ls -la /etc/<service>/`
5. Check dependencies: `systemctl list-dependencies <service>`
6. Test manually: Run service binary with debug flags

## Best Practices

1. **Always backup before making changes** - Create snapshots or backups of critical configurations
2. **Use sudo appropriately** - Don't run as root unnecessarily; use sudo for specific commands
3. **Document changes** - Keep notes of configuration modifications in `/root/CHANGES.log` or similar
4. **Test in non-production first** - Validate commands on test systems when possible
5. **Check logs after changes** - Always verify service logs after configuration changes
6. **Use version control for configs** - Track important configurations in git
7. **Keep systems updated** - Regularly apply security patches
8. **Monitor disk space** - Set up alerts for disk usage thresholds
9. **Use appropriate file permissions** - Follow principle of least privilege
10. **Enable firewall** - Always run a firewall with minimal required ports open

## Common Pitfalls

### General Administration
- Not checking distribution before running package manager commands
- Forgetting to reload/restart services after configuration changes
- Not backing up configuration files before editing
- Using `rm -rf` without double-checking the path
- Modifying SELinux/AppArmor without understanding implications
- Assuming commands work identically across distributions
- Neglecting to check logs after making changes

### Networking Specific
- Not testing firewall rules before disconnecting from remote session (lock yourself out)
- Changing network config on remote server without console access backup
- Applying tc (traffic control) rules on production without testing (can severely impact performance)
- Flushing iptables/nftables rules without saving first
- Enabling IP forwarding without proper firewall rules (creates open relay)
- Modifying MTU without understanding path MTU discovery implications
- Setting wrong VLAN ID or not trunking VLAN on switch side
- Forgetting to bring interfaces up after configuration changes
- Not testing bonding/teaming configuration before removing physical connections
- Misconfiguring bridge and losing network connectivity
- Using ethtool to force speed/duplex without matching switch config
- Applying network namespaces commands to wrong namespace
- Not saving iptables rules (lost on reboot unless configured)
- Setting up NAT without enabling IP forwarding in kernel
- Changing MAC address on interface with static DHCP reservation
- Testing network changes during business hours without maintenance window
- Not documenting custom routing tables and policy routing rules

## Reference Files

For more specialized topics, see the bundled reference files:
- `references/apache-nginx.md` - Web server configuration and troubleshooting
- `references/database.md` - MySQL/PostgreSQL administration
- `references/containers.md` - Docker and Podman management
- `references/monitoring.md` - Advanced monitoring and alerting setup
- `references/advanced-networking.md` - Deep-dive Layer 1-4 networking scenarios, SR-IOV, VRF, VXLAN, traffic shaping, and production troubleshooting