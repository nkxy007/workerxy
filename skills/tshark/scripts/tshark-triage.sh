#!/usr/bin/env bash
# tshark-triage.sh
# Quick NOC triage script for a pcap file.
# Usage: ./tshark-triage.sh <pcap_file> [output_dir]
#
# Runs a standard battery of tshark analyses and writes results to output_dir.
# Requires: tshark installed, readable pcap file.

set -euo pipefail

PCAP="${1:-}"
OUTDIR="${2:-./triage_$(date +%Y%m%d_%H%M%S)}"

if [[ -z "$PCAP" ]]; then
  echo "Usage: $0 <pcap_file> [output_dir]"
  exit 1
fi

if [[ ! -f "$PCAP" ]]; then
  echo "ERROR: File not found: $PCAP"
  exit 1
fi

command -v tshark >/dev/null 2>&1 || { echo "ERROR: tshark not found. Install with: dnf install wireshark-cli"; exit 1; }

mkdir -p "$OUTDIR"
echo "[triage] Analyzing: $PCAP"
echo "[triage] Output:    $OUTDIR"
echo ""

run() {
  local label="$1"; shift
  local outfile="$OUTDIR/${label}.txt"
  echo "[+] $label..."
  tshark "$@" > "$outfile" 2>&1 || true
}

# 1. Protocol hierarchy
run "01_protocol_hierarchy" -r "$PCAP" -q -z io,phs

# 2. IP conversations (top talkers)
run "02_ip_conversations" -r "$PCAP" -q -z conv,ip

# 3. TCP conversations
run "03_tcp_conversations" -r "$PCAP" -q -z conv,tcp

# 4. IP endpoints
run "04_ip_endpoints" -r "$PCAP" -q -z endpoints,ip

# 5. Expert info (anomalies summary)
run "05_expert_info" -r "$PCAP" -q -z expert

# 6. DNS queries (failures highlighted)
run "06_dns_queries" -r "$PCAP" -Y "dns" -T fields -E header=y \
  -e frame.time -e ip.src -e dns.qry.name -e dns.qry.type -e dns.flags.rcode

# 7. DNS NXDOMAIN
run "07_dns_nxdomain" -r "$PCAP" -Y "dns.flags.rcode == 3" -T fields -E header=y \
  -e frame.time -e ip.src -e dns.qry.name

# 8. TCP retransmissions
run "08_tcp_retransmissions" -r "$PCAP" -Y "tcp.analysis.retransmission" \
  -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst -e tcp.stream -e tcp.analysis.retransmission

# 9. TCP RST packets
run "09_tcp_rst" -r "$PCAP" -Y "tcp.flags.reset == 1" \
  -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst -e tcp.srcport -e tcp.dstport

# 10. ICMP unreachables
run "10_icmp_unreachable" -r "$PCAP" -Y "icmp.type == 3" \
  -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst -e icmp.type -e icmp.code

# 11. HTTP errors
run "11_http_errors" -r "$PCAP" -Y "http.response.code >= 400" \
  -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e http.response.code -e http.response.phrase -e http.host

# 12. TLS SNI (hostnames in HTTPS)
run "12_tls_sni" -r "$PCAP" -Y "tls.handshake.type == 1" \
  -T fields -E header=y \
  -e frame.time -e ip.src -e ip.dst \
  -e tls.handshake.extensions_server_name

# 13. Large frames (fragmentation / jumbo candidates)
run "13_large_frames" -r "$PCAP" -Y "frame.len > 1400" \
  -T fields -E header=y \
  -e frame.number -e frame.len -e ip.src -e ip.dst

# Summary
echo ""
echo "[triage] Done. Results written to: $OUTDIR"
ls -lh "$OUTDIR"/*.txt 2>/dev/null
