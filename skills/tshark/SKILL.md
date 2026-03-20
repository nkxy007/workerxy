---
name: tshark
description: Analyze network packets using tshark (Wireshark CLI). Use when the user wants to capture live traffic, read .pcap/.pcapng files, filter packets by protocol or field, extract specific fields, drill into packet details, or generate traffic statistics. Covers live capture, pcap file analysis, display filters, field extraction, protocol drill-down, conversation stats, flow analysis, and JSON/PDML output for programmatic processing.
compatibility: Requires tshark (Wireshark) installed. On CentOS/RHEL use `dnf install wireshark-cli`. Live capture requires root or CAP_NET_RAW. Reading pcap files works as any user.
allowed-tools: Bash
metadata:
  author: xtf
  version: "1.0"
  reference: https://www.wireshark.org/docs/man-pages/tshark.html
---

# tshark Packet Analysis Skill

`tshark` is the command-line interface for Wireshark — the industry-standard network protocol analyzer. It supports live capture, reading pcap/pcapng files, deep protocol dissection, field extraction, and rich statistics.

## Step 1 — Determine the analysis mode

| Mode | Scenario | Key option |
|------|----------|------------|
| **Read pcap file** | Analyze an existing capture | `-r <file>` |
| **Live capture** | Capture from a live interface | `-i <iface>` (requires root) |
| **Pipe input** | Read from stdin | `-r -` |

Always prefer reading a file when one is available — no privilege required and fully repeatable.

```bash
# List available interfaces (live capture)
tshark -D

# Read a pcap file
tshark -r capture.pcap

# Read compressed pcap (gzip/zstd/lz4 auto-detected)
tshark -r capture.pcap.gz
```

## Step 2 — Apply display filters (`-Y`)

Display filters are Wireshark syntax and are extremely powerful. Use `-Y` when reading a file or capturing live.

```bash
# Filter by protocol
tshark -r capture.pcap -Y "http"
tshark -r capture.pcap -Y "dns"
tshark -r capture.pcap -Y "tcp"

# Filter by IP address
tshark -r capture.pcap -Y "ip.addr == 192.168.1.1"
tshark -r capture.pcap -Y "ip.src == 10.0.0.1 && ip.dst == 10.0.0.2"

# Filter by port
tshark -r capture.pcap -Y "tcp.port == 443"
tshark -r capture.pcap -Y "udp.port == 53"

# Combine filters
tshark -r capture.pcap -Y "tcp.port == 80 || tcp.port == 443"
tshark -r capture.pcap -Y "http && ip.addr == 10.0.0.5"

# Filter TCP flags
tshark -r capture.pcap -Y "tcp.flags.syn == 1 && tcp.flags.ack == 0"

# Filter by DNS query name
tshark -r capture.pcap -Y 'dns.qry.name contains "example.com"'

# Filter HTTP status codes
tshark -r capture.pcap -Y "http.response.code >= 400"

# ICMP errors
tshark -r capture.pcap -Y "icmp.type == 3"
```

> **Capture filters vs display filters:** `-f` uses libpcap/BPF syntax (faster, for live capture only). `-Y` uses Wireshark display filter syntax (more powerful, works on files and live). Do not mix them — they are different languages.

## Step 3 — Drill into packet details

### View full packet decode (`-V`)
Shows all protocol layers and every field value.

```bash
# Full verbose decode of all packets
tshark -r capture.pcap -V

# Verbose decode with filter
tshark -r capture.pcap -Y "dns" -V

# Show only details for specific protocols, summary line for others (-O)
tshark -r capture.pcap -O http
tshark -r capture.pcap -O http,tcp
tshark -r capture.pcap -Y "http" -O http

# Show summary line AND full details (-P + -V)
tshark -r capture.pcap -P -V -Y "tcp.flags.syn == 1"
```

### Two-pass analysis (`-2`)
Enables cross-packet fields like "response in frame #" and better reassembly. Always use for file analysis when investigating request/response pairs.

```bash
tshark -r capture.pcap -2 -Y "http" -V
```

### Inspect a specific packet by frame number
```bash
tshark -r capture.pcap -Y "frame.number == 42" -V
```

## Step 4 — Extract specific fields (`-T fields -e`)

Extract structured data for scripting or reporting. Field names use Wireshark dot-notation.

```bash
# Basic field extraction
tshark -r capture.pcap -T fields -e frame.number -e frame.time -e ip.src -e ip.dst -e _ws.col.info

# With header row
tshark -r capture.pcap -T fields -E header=y -e ip.src -e ip.dst -e tcp.srcport -e tcp.dstport

# DNS query extraction
tshark -r capture.pcap -Y "dns.flags.response == 0" \
  -T fields -E header=y \
  -e frame.time -e ip.src -e dns.qry.name -e dns.qry.type

# HTTP requests
tshark -r capture.pcap -Y "http.request" \
  -T fields -E header=y \
  -e ip.src -e ip.dst -e http.host -e http.request.method -e http.request.uri

# TLS handshake - SNI extraction
tshark -r capture.pcap -Y "tls.handshake.type == 1" \
  -T fields -e ip.src -e ip.dst -e tls.handshake.extensions_server_name

# TCP connection timing
tshark -r capture.pcap -Y "tcp.flags.syn == 1 && tcp.flags.ack == 0" \
  -T fields -e frame.time -e ip.src -e ip.dst -e tcp.dstport

# Raw hex bytes of a field
tshark -r capture.pcap -T fields -e @ip.src -e @tcp.payload
```

**Field separator options (`-E`):**
```bash
-E separator=/t      # tab (default)
-E separator=/s      # space
-E separator=","     # comma (for CSV)
-E header=y          # print field names as first row
-E quote=d           # double-quote values
-E occurrence=f      # first occurrence only (for multi-value fields)
-E occurrence=a      # all occurrences (default)
```

## Step 5 — Output formats (`-T`)

| Format | Use case |
|--------|----------|
| `-T text` | Human-readable summary (default) |
| `-T fields` | Structured field extraction (with `-e`) |
| `-T json` | Full JSON decode, ideal for programmatic parsing |
| `-T pdml` | XML format, full protocol detail |
| `-T ek` | ElasticSearch/Kibana bulk JSON |
| `-T tabs` | Tab-separated summary |

```bash
# JSON output - full decode of filtered packets
tshark -r capture.pcap -Y "dns" -T json

# JSON for a specific frame
tshark -r capture.pcap -Y "frame.number == 10" -T json

# PDML (XML) output
tshark -r capture.pcap -Y "icmp" -T pdml
```

## Step 6 — Statistics and flow analysis (`-z`)

`-z` generates statistical summaries. Use `-q` to suppress per-packet output and show only stats.

```bash
# Protocol hierarchy breakdown
tshark -r capture.pcap -q -z io,phs

# Conversation table (IP pairs, bytes, packets)
tshark -r capture.pcap -q -z conv,ip
tshark -r capture.pcap -q -z conv,tcp
tshark -r capture.pcap -q -z conv,udp

# Endpoint statistics (top talkers)
tshark -r capture.pcap -q -z endpoints,ip
tshark -r capture.pcap -q -z endpoints,tcp

# HTTP request stats
tshark -r capture.pcap -q -z http,tree

# DNS query stats
tshark -r capture.pcap -q -z dns,tree

# TCP stream follow (reassemble full conversation)
tshark -r capture.pcap -q -z follow,tcp,ascii,0     # stream index 0
tshark -r capture.pcap -q -z follow,http,ascii,0
tshark -r capture.pcap -q -z follow,udp,ascii,0

# I/O graph (bytes per second, time-bucketed)
tshark -r capture.pcap -q -z io,stat,1              # 1-second buckets
tshark -r capture.pcap -q -z io,stat,0.1,"ip.src==10.0.0.1"

# Expert info (errors, warnings, notes)
tshark -r capture.pcap -q -z expert

# SIP call stats
tshark -r capture.pcap -q -z sip,stat
```

See [references/statistics.md](references/statistics.md) for full `-z` option reference.

## Step 7 — Live capture

```bash
# Capture on interface eth0, 100 packets
tshark -i eth0 -c 100

# Capture with BPF filter and save to file
tshark -i eth0 -f "tcp port 80" -w /tmp/http.pcap

# Capture and display verbose output simultaneously
tshark -i eth0 -P -V -f "icmp"

# Auto-stop conditions
tshark -i eth0 -a duration:60 -w /tmp/capture.pcap    # stop after 60 seconds
tshark -i eth0 -a filesize:10240 -w /tmp/capture.pcap # stop after 10 MB
tshark -i eth0 -a packets:1000 -w /tmp/capture.pcap   # stop after 1000 packets

# Ring buffer (5 files × 10 MB)
tshark -i eth0 -b filesize:10240 -b files:5 -w /tmp/ring.pcap
```

## Step 8 — Protocol-specific drill-down patterns

See [references/protocols.md](references/protocols.md) for ready-to-use filter and field recipes per protocol.

### Quick reference — common protocols

| Protocol | Display filter | Key fields |
|----------|---------------|------------|
| DNS | `dns` | `dns.qry.name`, `dns.qry.type`, `dns.resp.addr` |
| HTTP | `http` | `http.host`, `http.request.uri`, `http.response.code` |
| TLS/HTTPS | `tls` | `tls.handshake.extensions_server_name`, `tls.record.version` |
| DHCP | `dhcp` | `dhcp.option.hostname`, `dhcp.option.requested_ip_address` |
| ICMP | `icmp` | `icmp.type`, `icmp.code` |
| ARP | `arp` | `arp.src.hw_mac`, `arp.src.proto_ipv4` |
| OSPF | `ospf` | `ospf.msg`, `ospf.srcrouter` |
| BGP | `bgp` | `bgp.type`, `bgp.prefix_length` |
| SNMP | `snmp` | `snmp.name`, `snmp.value` |
| STP | `stp` | `stp.root.hw`, `stp.bridge.hw` |
| VLAN | `vlan` | `vlan.id`, `vlan.priority` |
| MPLS | `mpls` | `mpls.label`, `mpls.ttl` |

## Step 9 — Discover field names

When you need the exact field name for filtering or `-e` extraction:

```bash
# List all protocols
tshark -G protocols | grep -i "http"

# Find fields for a protocol
tshark -G fields | grep "^F" | awk -F'\t' '$5=="http"'

# Search field names by keyword
tshark -G fields | grep -i "dns.qry"
tshark -G fields | grep -i "tls.handshake"

# Find all fields for a specific protocol abbreviation
tshark -G fields | awk -F'\t' '$5=="tcp" {print $3, $2}'
```

## Common workflows for the NOC agent

```bash
# 1. Quick triage — what protocols are in this capture?
tshark -r capture.pcap -q -z io,phs

# 2. Who are the top talkers?
tshark -r capture.pcap -q -z conv,ip | sort -k1 -rn | head -20

# 3. Are there TCP retransmissions (congestion indicator)?
tshark -r capture.pcap -Y "tcp.analysis.retransmission" -T fields \
  -E header=y -e frame.time -e ip.src -e ip.dst -e tcp.stream

# 4. Any ICMP unreachables (routing or firewall drops)?
tshark -r capture.pcap -Y "icmp.type == 3" -V

# 5. DNS failures (NXDOMAIN)?
tshark -r capture.pcap -Y "dns.flags.rcode == 3" \
  -T fields -e frame.time -e ip.src -e dns.qry.name

# 6. Follow a specific TCP stream
tshark -r capture.pcap -q -z follow,tcp,ascii,<stream_index>

# 7. Extract all unique destination IPs
tshark -r capture.pcap -T fields -e ip.dst | sort -u

# 8. Count packets per source IP
tshark -r capture.pcap -T fields -e ip.src | sort | uniq -c | sort -rn

# 9. Find large packets (potential fragmentation issues)
tshark -r capture.pcap -Y "frame.len > 1400" -T fields \
  -e frame.number -e frame.len -e ip.src -e ip.dst

# 10. Expert info summary (all protocol anomalies)
tshark -r capture.pcap -q -z expert
```

## Error handling

| Error | Cause | Fix |
|-------|-------|-----|
| `permission denied` on capture | No root / no CAP_NET_RAW | Run as root or `sudo setcap cap_net_raw+eip $(which tshark)` |
| `tshark: command not found` | Not installed | `dnf install wireshark-cli` (CentOS/RHEL) |
| `The file "x" doesn't exist` | Wrong path | Check path; use `ls -la` to verify |
| Filter syntax error | Wrong filter syntax | Check with `tshark -Y "..." --dry-run` or use `-G fields` to verify field names |
| Empty output | Filter too restrictive | Relax filter; check packet count with `tshark -r file.pcap | wc -l` |