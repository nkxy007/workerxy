# tshark Protocol Reference

Deep-dive filter and field extraction recipes organized by protocol. Reference from SKILL.md Step 8.

---

## TCP

```bash
# TCP connection lifecycle
tshark -r cap.pcap -Y "tcp.flags.syn == 1 && tcp.flags.ack == 0"   # SYN (connection initiation)
tshark -r cap.pcap -Y "tcp.flags.syn == 1 && tcp.flags.ack == 1"   # SYN-ACK
tshark -r cap.pcap -Y "tcp.flags.fin == 1"                          # FIN (graceful close)
tshark -r cap.pcap -Y "tcp.flags.reset == 1"                        # RST (abrupt close)

# TCP performance anomalies
tshark -r cap.pcap -Y "tcp.analysis.retransmission"                  # Retransmissions
tshark -r cap.pcap -Y "tcp.analysis.fast_retransmission"             # Fast retransmissions
tshark -r cap.pcap -Y "tcp.analysis.duplicate_ack"                   # Duplicate ACKs
tshark -r cap.pcap -Y "tcp.analysis.zero_window"                     # Zero window (receiver overwhelmed)
tshark -r cap.pcap -Y "tcp.analysis.window_full"                     # Sender hit window limit
tshark -r cap.pcap -Y "tcp.analysis.out_of_order"                    # Out-of-order segments
tshark -r cap.pcap -Y "tcp.analysis.lost_segment"                    # Lost segment detected

# Extract TCP stream data
tshark -r cap.pcap -T fields -e tcp.stream -e ip.src -e ip.dst \
  -e tcp.srcport -e tcp.dstport | sort -u                            # List all TCP streams

# Follow a stream (replace 0 with stream index)
tshark -r cap.pcap -q -z follow,tcp,ascii,0

# TCP RTT measurement
tshark -r cap.pcap -Y "tcp.analysis.ack_rtt" \
  -T fields -e frame.time -e ip.src -e ip.dst -e tcp.analysis.ack_rtt
```

---

## UDP

```bash
# All UDP traffic
tshark -r cap.pcap -Y "udp"

# Specific ports
tshark -r cap.pcap -Y "udp.dstport == 53"     # DNS
tshark -r cap.pcap -Y "udp.dstport == 161"    # SNMP
tshark -r cap.pcap -Y "udp.dstport == 514"    # Syslog
tshark -r cap.pcap -Y "udp.dstport == 4789"   # VXLAN

# Large UDP datagrams (potential fragmentation)
tshark -r cap.pcap -Y "udp && frame.len > 1400"
```

---

## DNS

```bash
# All queries (not responses)
tshark -r cap.pcap -Y "dns.flags.response == 0"

# All responses
tshark -r cap.pcap -Y "dns.flags.response == 1"

# NXDOMAIN (non-existent domain)
tshark -r cap.pcap -Y "dns.flags.rcode == 3"

# Specific query types
tshark -r cap.pcap -Y "dns.qry.type == 1"    # A record
tshark -r cap.pcap -Y "dns.qry.type == 28"   # AAAA record
tshark -r cap.pcap -Y "dns.qry.type == 5"    # CNAME
tshark -r cap.pcap -Y "dns.qry.type == 15"   # MX
tshark -r cap.pcap -Y "dns.qry.type == 33"   # SRV
tshark -r cap.pcap -Y "dns.qry.type == 255"  # ANY (often abuse indicator)

# Query name matching
tshark -r cap.pcap -Y 'dns.qry.name contains "example.com"'
tshark -r cap.pcap -Y 'dns.qry.name matches ".*\\.internal$"'

# Extract DNS query/response pairs
tshark -r cap.pcap -Y "dns" -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e dns.qry.name -e dns.qry.type -e dns.flags.rcode -e dns.resp.addr

# Statistics tree
tshark -r cap.pcap -q -z dns,tree
```

---

## HTTP / HTTP2

```bash
# HTTP requests
tshark -r cap.pcap -Y "http.request"
tshark -r cap.pcap -Y "http.request.method == \"GET\""
tshark -r cap.pcap -Y "http.request.method == \"POST\""

# HTTP responses by status code
tshark -r cap.pcap -Y "http.response.code == 200"
tshark -r cap.pcap -Y "http.response.code >= 400"      # Client/server errors
tshark -r cap.pcap -Y "http.response.code >= 500"      # Server errors only

# Extract HTTP details
tshark -r cap.pcap -Y "http.request" -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e http.host -e http.request.method -e http.request.uri \
  -e http.user_agent

# Responses with content type
tshark -r cap.pcap -Y "http.response" -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e http.response.code -e http.content_type -e http.content_length

# HTTP statistics
tshark -r cap.pcap -q -z http,tree
tshark -r cap.pcap -q -z http_req,tree
tshark -r cap.pcap -q -z http_srv,tree

# Follow HTTP stream
tshark -r cap.pcap -q -z follow,http,ascii,0
```

---

## TLS / HTTPS

```bash
# TLS handshake types
# 1=ClientHello, 2=ServerHello, 11=Certificate, 12=ServerKeyExchange,
# 14=ServerHelloDone, 16=ClientKeyExchange, 20=Finished

tshark -r cap.pcap -Y "tls.handshake.type == 1"   # ClientHello
tshark -r cap.pcap -Y "tls.handshake.type == 2"   # ServerHello

# SNI (Server Name Indication) - reveals target hostname even in encrypted traffic
tshark -r cap.pcap -Y "tls.handshake.type == 1" \
  -T fields -e ip.src -e ip.dst -e tls.handshake.extensions_server_name

# TLS versions negotiated
tshark -r cap.pcap -Y "tls.handshake.type == 2" \
  -T fields -e ip.src -e ip.dst -e tls.handshake.version

# Certificate details
tshark -r cap.pcap -Y "tls.handshake.type == 11" \
  -T fields -e ip.src -e ip.dst \
  -e tls.handshake.certificate -e x509sat.uTF8String

# TLS alerts (errors / connection failures)
tshark -r cap.pcap -Y "tls.alert_message"
tshark -r cap.pcap -Y "tls.record.content_type == 21"   # alert content type

# Cipher suites offered by client
tshark -r cap.pcap -Y "tls.handshake.type == 1" -V -O tls | grep "Cipher Suite"
```

---

## ICMP / ICMPv6

```bash
# ICMP types
# 0=Echo Reply, 3=Destination Unreachable, 4=Source Quench,
# 5=Redirect, 8=Echo Request, 11=Time Exceeded

tshark -r cap.pcap -Y "icmp.type == 8"     # Echo Request (ping)
tshark -r cap.pcap -Y "icmp.type == 0"     # Echo Reply
tshark -r cap.pcap -Y "icmp.type == 3"     # Destination Unreachable
tshark -r cap.pcap -Y "icmp.type == 11"    # TTL Exceeded (traceroute)

# Destination unreachable codes
# 0=Net, 1=Host, 2=Protocol, 3=Port, 4=Frag needed, 13=Admin prohibited
tshark -r cap.pcap -Y "icmp.type == 3 && icmp.code == 1"    # Host unreachable
tshark -r cap.pcap -Y "icmp.type == 3 && icmp.code == 3"    # Port unreachable
tshark -r cap.pcap -Y "icmp.type == 3 && icmp.code == 13"   # Admin prohibited (firewall)

# Extract ICMP fields
tshark -r cap.pcap -Y "icmp" -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst -e icmp.type -e icmp.code

# ICMPv6
tshark -r cap.pcap -Y "icmpv6.type == 135"   # Neighbor Solicitation
tshark -r cap.pcap -Y "icmpv6.type == 136"   # Neighbor Advertisement
tshark -r cap.pcap -Y "icmpv6.type == 133"   # Router Solicitation
tshark -r cap.pcap -Y "icmpv6.type == 134"   # Router Advertisement
```

---

## ARP

```bash
# ARP requests (who-has)
tshark -r cap.pcap -Y "arp.opcode == 1"

# ARP replies (is-at)
tshark -r cap.pcap -Y "arp.opcode == 2"

# Gratuitous ARP (potential conflict indicator)
tshark -r cap.pcap -Y "arp.isgratuitous == 1"

# ARP fields
tshark -r cap.pcap -Y "arp" -T fields -E header=y \
  -e frame.time -e arp.src.hw_mac -e arp.src.proto_ipv4 \
  -e arp.dst.hw_mac -e arp.dst.proto_ipv4 -e arp.opcode

# Find duplicate IPs (ARP poisoning indicator)
tshark -r cap.pcap -Y "arp" -T fields -e arp.src.proto_ipv4 -e arp.src.hw_mac \
  | sort | uniq -D
```

---

## DHCP

```bash
# DHCP message types
# 1=Discover, 2=Offer, 3=Request, 4=Decline, 5=ACK, 6=NAK, 7=Release, 8=Inform

tshark -r cap.pcap -Y "dhcp.option.dhcp == 1"    # DISCOVER
tshark -r cap.pcap -Y "dhcp.option.dhcp == 2"    # OFFER
tshark -r cap.pcap -Y "dhcp.option.dhcp == 3"    # REQUEST
tshark -r cap.pcap -Y "dhcp.option.dhcp == 5"    # ACK
tshark -r cap.pcap -Y "dhcp.option.dhcp == 6"    # NAK (failure)

# Extract DHCP info
tshark -r cap.pcap -Y "dhcp" -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e dhcp.option.dhcp \
  -e dhcp.option.hostname \
  -e dhcp.option.requested_ip_address \
  -e dhcp.option.dhcp_server_id \
  -e dhcp.hw.mac_addr
```

---

## VLAN / 802.1Q

```bash
# All VLAN-tagged frames
tshark -r cap.pcap -Y "vlan"

# Specific VLAN ID
tshark -r cap.pcap -Y "vlan.id == 100"

# Frames with priority tagging
tshark -r cap.pcap -Y "vlan.priority > 0"

# Extract VLAN info
tshark -r cap.pcap -Y "vlan" -T fields -E header=y \
  -e frame.time -e eth.src -e eth.dst \
  -e vlan.id -e vlan.priority -e vlan.etype
```

---

## OSPF

```bash
# OSPF message types
# 1=Hello, 2=DBD, 3=LSR, 4=LSU, 5=LSAck

tshark -r cap.pcap -Y "ospf"
tshark -r cap.pcap -Y "ospf.msg == 1"    # Hello packets
tshark -r cap.pcap -Y "ospf.msg == 4"    # LSU (topology updates)

# Extract OSPF info
tshark -r cap.pcap -Y "ospf" -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e ospf.msg -e ospf.srcrouter -e ospf.areaid \
  -e ospf.hello.router_dead_interval
```

---

## BGP

```bash
# BGP message types
# 1=OPEN, 2=UPDATE, 3=NOTIFICATION, 4=KEEPALIVE

tshark -r cap.pcap -Y "bgp"
tshark -r cap.pcap -Y "bgp.type == 2"    # UPDATE (route changes)
tshark -r cap.pcap -Y "bgp.type == 3"    # NOTIFICATION (errors)

# Extract BGP updates
tshark -r cap.pcap -Y "bgp.type == 2" -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e bgp.prefix_length -e bgp.mp_reach_nlri_ipv4_prefix

# BGP error codes (NOTIFICATION)
tshark -r cap.pcap -Y "bgp.type == 3" -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e bgp.notify.major_error -e bgp.notify.minor_error
```

---

## SNMP

```bash
# SNMP versions and types
tshark -r cap.pcap -Y "snmp"
tshark -r cap.pcap -Y "snmp.version == 0"    # SNMPv1
tshark -r cap.pcap -Y "snmp.version == 1"    # SNMPv2c
tshark -r cap.pcap -Y "snmp.version == 3"    # SNMPv3

# SNMP traps/informs
tshark -r cap.pcap -Y "snmp && udp.dstport == 162"

# Extract OID and values
tshark -r cap.pcap -Y "snmp" -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e snmp.name -e snmp.value.integer -e snmp.value.octets

# SNMP communities (v1/v2c — visible in clear text)
tshark -r cap.pcap -Y "snmp" -T fields -e snmp.community
```

---

## STP / RSTP

```bash
# STP topology changes
tshark -r cap.pcap -Y "stp.flags.tc == 1"        # Topology Change
tshark -r cap.pcap -Y "stp.flags.tca == 1"       # Topology Change Acknowledgement

# STP root bridge info
tshark -r cap.pcap -Y "stp" -T fields -E header=y \
  -e frame.time -e eth.src -e stp.root.hw \
  -e stp.root.cost -e stp.bridge.hw -e stp.port
```

---

## Multicast / IGMP

```bash
# IGMP membership
tshark -r cap.pcap -Y "igmp"
tshark -r cap.pcap -Y "igmp.type == 0x16"    # IGMPv2 Membership Report
tshark -r cap.pcap -Y "igmp.type == 0x17"    # IGMPv2 Leave Group

# Multicast traffic
tshark -r cap.pcap -Y "ip.dst >= 224.0.0.0 && ip.dst <= 239.255.255.255"
```

---

## VoIP / RTP / SIP

```bash
# SIP signaling
tshark -r cap.pcap -Y "sip"
tshark -r cap.pcap -Y "sip.Method == \"INVITE\""
tshark -r cap.pcap -Y "sip.Status-Code >= 400"    # SIP errors

# RTP media streams
tshark -r cap.pcap -Y "rtp"

# SIP/RTP statistics
tshark -r cap.pcap -q -z sip,stat
tshark -r cap.pcap -q -z rtp,streams
```
