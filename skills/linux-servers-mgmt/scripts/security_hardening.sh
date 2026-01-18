#!/bin/bash

# Server Security Hardening Script
# Applies common security best practices to Ubuntu/RedHat servers

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}" 
   exit 1
fi

echo "========================================="
echo "Server Security Hardening Script"
echo "========================================="

# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo -e "${RED}Cannot detect distribution${NC}"
    exit 1
fi

echo "Detected distribution: $DISTRO"
echo ""

# Update system
echo -e "${GREEN}[1/10] Updating system packages...${NC}"
if [ "$DISTRO" = "ubuntu" ] || [ "$DISTRO" = "debian" ]; then
    apt update && apt upgrade -y
elif [ "$DISTRO" = "rhel" ] || [ "$DISTRO" = "centos" ] || [ "$DISTRO" = "rocky" ] || [ "$DISTRO" = "almalinux" ]; then
    dnf upgrade -y
fi

# Configure automatic security updates
echo -e "${GREEN}[2/10] Configuring automatic security updates...${NC}"
if [ "$DISTRO" = "ubuntu" ] || [ "$DISTRO" = "debian" ]; then
    apt install unattended-upgrades -y
    dpkg-reconfigure -plow unattended-upgrades
elif [ "$DISTRO" = "rhel" ] || [ "$DISTRO" = "centos" ] || [ "$DISTRO" = "rocky" ] || [ "$DISTRO" = "almalinux" ]; then
    dnf install dnf-automatic -y
    sed -i 's/apply_updates = no/apply_updates = yes/' /etc/dnf/automatic.conf
    systemctl enable --now dnf-automatic.timer
fi

# SSH Hardening
echo -e "${GREEN}[3/10] Hardening SSH configuration...${NC}"
SSH_CONFIG="/etc/ssh/sshd_config"

# Backup original config
cp $SSH_CONFIG ${SSH_CONFIG}.backup.$(date +%Y%m%d)

# Apply SSH hardening settings
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' $SSH_CONFIG
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' $SSH_CONFIG
sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' $SSH_CONFIG
sed -i 's/^#*X11Forwarding.*/X11Forwarding no/' $SSH_CONFIG
sed -i 's/^#*MaxAuthTries.*/MaxAuthTries 3/' $SSH_CONFIG

# Add additional hardening if not present
grep -q "^ClientAliveInterval" $SSH_CONFIG || echo "ClientAliveInterval 300" >> $SSH_CONFIG
grep -q "^ClientAliveCountMax" $SSH_CONFIG || echo "ClientAliveCountMax 2" >> $SSH_CONFIG
grep -q "^Protocol" $SSH_CONFIG || echo "Protocol 2" >> $SSH_CONFIG

systemctl restart sshd

# Configure firewall
echo -e "${GREEN}[4/10] Configuring firewall...${NC}"
if [ "$DISTRO" = "ubuntu" ] || [ "$DISTRO" = "debian" ]; then
    apt install ufw -y
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw --force enable
elif [ "$DISTRO" = "rhel" ] || [ "$DISTRO" = "centos" ] || [ "$DISTRO" = "rocky" ] || [ "$DISTRO" = "almalinux" ]; then
    systemctl enable --now firewalld
    firewall-cmd --set-default-zone=public
    firewall-cmd --permanent --add-service=ssh
    firewall-cmd --reload
fi

# Disable unnecessary services
echo -e "${GREEN}[5/10] Disabling unnecessary services...${NC}"
SERVICES_TO_DISABLE=("avahi-daemon" "cups" "bluetooth")
for service in "${SERVICES_TO_DISABLE[@]}"; do
    if systemctl is-enabled "$service" 2>/dev/null | grep -q enabled; then
        systemctl disable --now "$service" 2>/dev/null || true
        echo "Disabled $service"
    fi
done

# Set up fail2ban
echo -e "${GREEN}[6/10] Installing and configuring fail2ban...${NC}"
if [ "$DISTRO" = "ubuntu" ] || [ "$DISTRO" = "debian" ]; then
    apt install fail2ban -y
elif [ "$DISTRO" = "rhel" ] || [ "$DISTRO" = "centos" ] || [ "$DISTRO" = "rocky" ] || [ "$DISTRO" = "almalinux" ]; then
    dnf install epel-release -y
    dnf install fail2ban -y
fi

cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
logpath = %(sshd_log)s
backend = %(sshd_backend)s
EOF

systemctl enable --now fail2ban

# Kernel hardening
echo -e "${GREEN}[7/10] Applying kernel hardening parameters...${NC}"
cat > /etc/sysctl.d/99-security.conf << 'EOF'
# IP Forwarding
net.ipv4.ip_forward = 0
net.ipv6.conf.all.forwarding = 0

# Ignore ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0

# Ignore send redirects
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# Disable source packet routing
net.ipv4.conf.all.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv6.conf.default.accept_source_route = 0

# Log Martians
net.ipv4.conf.all.log_martians = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1

# Ignore ICMP ping requests
net.ipv4.icmp_echo_ignore_all = 0

# Ignore Directed pings
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Accept Redirects? No
net.ipv4.conf.all.secure_redirects = 0

# TCP/IP stack hardening
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_rfc1337 = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
EOF

sysctl -p /etc/sysctl.d/99-security.conf

# Set secure file permissions
echo -e "${GREEN}[8/10] Setting secure file permissions...${NC}"
chmod 644 /etc/passwd
chmod 644 /etc/group
chmod 600 /etc/shadow
chmod 600 /etc/gshadow
chmod 644 /etc/ssh/sshd_config

# Install and configure auditd
echo -e "${GREEN}[9/10] Installing audit daemon...${NC}"
if [ "$DISTRO" = "ubuntu" ] || [ "$DISTRO" = "debian" ]; then
    apt install auditd audispd-plugins -y
elif [ "$DISTRO" = "rhel" ] || [ "$DISTRO" = "centos" ] || [ "$DISTRO" = "rocky" ] || [ "$DISTRO" = "almalinux" ]; then
    dnf install audit -y
fi
systemctl enable --now auditd

# Create security monitoring cron job
echo -e "${GREEN}[10/10] Setting up security monitoring...${NC}"
cat > /etc/cron.daily/security-check << 'EOF'
#!/bin/bash
# Daily security check

echo "Security Check - $(date)" >> /var/log/security-check.log

# Check for failed login attempts
echo "Failed login attempts:" >> /var/log/security-check.log
if [ -f /var/log/auth.log ]; then
    grep "Failed password" /var/log/auth.log | tail -10 >> /var/log/security-check.log
elif command -v journalctl &> /dev/null; then
    journalctl -u sshd | grep "Failed password" | tail -10 >> /var/log/security-check.log
fi

# Check for sudo usage
echo "Recent sudo usage:" >> /var/log/security-check.log
if [ -f /var/log/auth.log ]; then
    grep "sudo:" /var/log/auth.log | tail -10 >> /var/log/security-check.log
elif command -v journalctl &> /dev/null; then
    journalctl | grep "sudo:" | tail -10 >> /var/log/security-check.log
fi

echo "---" >> /var/log/security-check.log
EOF

chmod +x /etc/cron.daily/security-check

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Security Hardening Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Summary of changes:"
echo "✓ System packages updated"
echo "✓ Automatic security updates enabled"
echo "✓ SSH hardened (root login disabled, password auth disabled)"
echo "✓ Firewall configured"
echo "✓ Unnecessary services disabled"
echo "✓ Fail2ban installed and configured"
echo "✓ Kernel parameters hardened"
echo "✓ File permissions secured"
echo "✓ Audit daemon enabled"
echo "✓ Daily security monitoring configured"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo "1. Ensure SSH key-based authentication is working before logging out"
echo "2. Review firewall rules and add necessary services"
echo "3. Check /var/log/security-check.log for daily security reports"
echo "4. Original SSH config backed up to ${SSH_CONFIG}.backup.$(date +%Y%m%d)"
echo ""