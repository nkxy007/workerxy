# tshark Statistics Reference (`-z` options)

Full reference for `-z` statistics options. Always combine with `-q` when using statistics to suppress per-packet output (unless you also want packet details).

---

## I/O Statistics

```bash
# Overall I/O statistics (bytes/packets per time interval)
tshark -r cap.pcap -q -z io,stat,0                   # entire capture as one interval
tshark -r cap.pcap -q -z io,stat,1                   # 1-second buckets
tshark -r cap.pcap -q -z io,stat,0.5                 # 0.5-second buckets

# With a display filter applied to the stat
tshark -r cap.pcap -q -z io,stat,1,"tcp.analysis.retransmission"

# Multiple filter columns side by side
tshark -r cap.pcap -q -z \
  'io,stat,1,,"tcp","udp","icmp"'

# Protocol hierarchy (breakdown of all protocols by byte/packet count)
tshark -r cap.pcap -q -z io,phs
```

---

## Conversation Statistics

Shows pairs of communicating endpoints with packet/byte counts and duration.

```bash
tshark -r cap.pcap -q -z conv,eth         # Ethernet-level
tshark -r cap.pcap -q -z conv,ip          # IP pairs
tshark -r cap.pcap -q -z conv,tcp         # TCP flows (5-tuple)
tshark -r cap.pcap -q -z conv,udp         # UDP flows
tshark -r cap.pcap -q -z conv,ipv6        # IPv6 pairs

# With display filter
tshark -r cap.pcap -q -z conv,tcp,"tcp.port==443"
```

---

## Endpoint Statistics

Shows per-endpoint (host/port) totals.

```bash
tshark -r cap.pcap -q -z endpoints,eth
tshark -r cap.pcap -q -z endpoints,ip
tshark -r cap.pcap -q -z endpoints,tcp
tshark -r cap.pcap -q -z endpoints,udp
tshark -r cap.pcap -q -z endpoints,ipv6
```

---

## Stream Follow

Reassembles and displays the full content of a connection.

```bash
# Formats: ascii | ebcdic | hex | raw
# Stream index from: tshark -r file.pcap -T fields -e tcp.stream | sort -un

tshark -r cap.pcap -q -z follow,tcp,ascii,0       # stream index 0, ASCII
tshark -r cap.pcap -q -z follow,tcp,hex,0         # stream index 0, hex
tshark -r cap.pcap -q -z follow,http,ascii,0      # HTTP stream reassembly
tshark -r cap.pcap -q -z follow,udp,ascii,0       # UDP flow
tshark -r cap.pcap -q -z follow,tls,ascii,0       # TLS (requires key log file)
```

---

## Protocol-Specific Statistics

```bash
# HTTP
tshark -r cap.pcap -q -z http,tree                # Request/response method breakdown
tshark -r cap.pcap -q -z http_req,tree            # HTTP request URIs
tshark -r cap.pcap -q -z http_srv,tree            # HTTP server responses

# DNS
tshark -r cap.pcap -q -z dns,tree                 # Query type / rcode breakdown

# SIP (VoIP signaling)
tshark -r cap.pcap -q -z sip,stat                 # SIP method/response counts

# RTP (VoIP media)
tshark -r cap.pcap -q -z rtp,streams              # RTP stream summary (SSRC, codec, jitter, loss)

# SMB/CIFS
tshark -r cap.pcap -q -z smb,rtt                  # SMB round-trip times
tshark -r cap.pcap -q -z smb,sids                 # SMB security identifiers

# DCERPC
tshark -r cap.pcap -q -z dcerpc,rtt               # DCE-RPC response times
```

---

## Expert Information

Wireshark classifies anomalies into: **Error**, **Warning**, **Note**, **Chat**.

```bash
# Summary of all expert info groups
tshark -r cap.pcap -q -z expert

# Expert info detail (full packet decode)
tshark -r cap.pcap -q -z expert -V
```

Expert error categories include:
- **tcp.analysis.retransmission** — Retransmitted segments
- **tcp.analysis.out_of_order** — Out-of-order delivery
- **tcp.analysis.zero_window** — Receiver window exhausted
- **tcp.analysis.lost_segment** — Dropped segments
- **icmp.unreach** — ICMP unreachable messages
- **dns.flags.rcode** — DNS error responses

---

## Flow Graphs and Timing

```bash
# TCP sequence analysis (flow graph data)
tshark -r cap.pcap -q -z flow,tcp,network

# Service response time (generic)
tshark -r cap.pcap -q -z "srt,dcerpc,<uuid>,<ver>"

# LDAP response times
tshark -r cap.pcap -q -z ldap,srt

# RADIUS response times
tshark -r cap.pcap -q -z radius,srt
```

---

## Output Tips

```bash
# Suppress per-packet lines, show only stats
tshark -r cap.pcap -q -z io,phs

# Combine multiple -z options in one pass
tshark -r cap.pcap -q -z io,phs -z conv,ip -z endpoints,tcp

# Apply display filter to scope the stats
tshark -r cap.pcap -q -z conv,tcp -Y "tcp.port == 443"
# Note: -Y applies to displayed packets; -z filter string applies to the stat itself

# Write filtered packets to new file while generating stats
tshark -r cap.pcap -Y "http" -w filtered_http.pcap -q -z http,tree
```
