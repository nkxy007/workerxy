#!/bin/bash

# System Health Check Script
# Performs comprehensive server health diagnostics

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script should be run as root for full diagnostics${NC}" 
   echo "Run with: sudo $0"
fi

echo "========================================="
echo "System Health Check Report"
echo "Date: $(date)"
echo "========================================="

# System Information
echo -e "\n${GREEN}=== SYSTEM INFORMATION ===${NC}"
echo "Hostname: $(hostname)"
echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "Kernel: $(uname -r)"
echo "Uptime: $(uptime -p)"

# CPU Usage
echo -e "\n${GREEN}=== CPU USAGE ===${NC}"
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
echo "CPU Usage: ${CPU_USAGE}%"
if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
    echo -e "${RED}WARNING: High CPU usage detected!${NC}"
fi

# Memory Usage
echo -e "\n${GREEN}=== MEMORY USAGE ===${NC}"
free -h
MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100)}')
echo "Memory Usage: ${MEMORY_USAGE}%"
if [ "$MEMORY_USAGE" -gt 90 ]; then
    echo -e "${RED}WARNING: High memory usage detected!${NC}"
fi

# Disk Usage
echo -e "\n${GREEN}=== DISK USAGE ===${NC}"
df -h | grep -vE '^Filesystem|tmpfs|cdrom'
DISK_ALERT=false
while IFS= read -r line; do
    USAGE=$(echo "$line" | awk '{print $5}' | sed 's/%//')
    MOUNT=$(echo "$line" | awk '{print $6}')
    if [ "$USAGE" -gt 85 ]; then
        echo -e "${RED}WARNING: ${MOUNT} is ${USAGE}% full${NC}"
        DISK_ALERT=true
    fi
done < <(df -h | grep -vE '^Filesystem|tmpfs|cdrom')

# Load Average
echo -e "\n${GREEN}=== LOAD AVERAGE ===${NC}"
LOAD=$(uptime | awk -F'load average:' '{print $2}')
echo "Load Average:$LOAD"

# Network Interfaces
echo -e "\n${GREEN}=== NETWORK INTERFACES ===${NC}"
ip -brief addr show

# Top 5 Processes by CPU
echo -e "\n${GREEN}=== TOP 5 PROCESSES (CPU) ===${NC}"
ps aux --sort=-%cpu | head -6

# Top 5 Processes by Memory
echo -e "\n${GREEN}=== TOP 5 PROCESSES (MEMORY) ===${NC}"
ps aux --sort=-%mem | head -6

# Failed Services
echo -e "\n${GREEN}=== FAILED SERVICES ===${NC}"
FAILED=$(systemctl --failed --no-pager --no-legend | wc -l)
if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}$FAILED failed services detected:${NC}"
    systemctl --failed --no-pager --no-legend
else
    echo "No failed services"
fi

# Last Logins
echo -e "\n${GREEN}=== LAST 5 LOGINS ===${NC}"
last -5 -w

# Last 10 Errors in Syslog
echo -e "\n${GREEN}=== RECENT ERRORS IN LOGS ===${NC}"
if [ -f /var/log/syslog ]; then
    echo "From /var/log/syslog:"
    grep -i error /var/log/syslog | tail -5 || echo "No recent errors found"
elif command -v journalctl &> /dev/null; then
    echo "From journalctl:"
    journalctl -p err -n 5 --no-pager || echo "No recent errors found"
fi

# Check for updates
echo -e "\n${GREEN}=== SYSTEM UPDATES ===${NC}"
if command -v apt &> /dev/null; then
    apt list --upgradable 2>/dev/null | grep -c upgradable || echo "System is up to date"
elif command -v dnf &> /dev/null; then
    dnf check-update --quiet | grep -v "^$" | wc -l || echo "System is up to date"
fi

# Summary
echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}HEALTH CHECK SUMMARY${NC}"
echo -e "${GREEN}=========================================${NC}"

ISSUES=0
if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
    echo -e "${RED}✗ High CPU usage${NC}"
    ((ISSUES++))
fi

if [ "$MEMORY_USAGE" -gt 90 ]; then
    echo -e "${RED}✗ High memory usage${NC}"
    ((ISSUES++))
fi

if [ "$DISK_ALERT" = true ]; then
    echo -e "${RED}✗ Low disk space${NC}"
    ((ISSUES++))
fi

if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}✗ Failed services detected${NC}"
    ((ISSUES++))
fi

if [ "$ISSUES" -eq 0 ]; then
    echo -e "${GREEN}✓ All systems nominal${NC}"
else
    echo -e "${YELLOW}⚠ $ISSUES issue(s) detected - review above${NC}"
fi

echo ""