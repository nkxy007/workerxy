import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from custom_middleware.netpii_middlewares import (
    suppress_credentials,
    NetCredentialSuppressorMiddleware
)

def test_cisco_user_enable_redaction():
    text = "username admin privilege 15 secret 5 $1$EEar$abc\nenable secret 9 $9$xyz\nusername ops password cleartext"
    redacted, mapping = suppress_credentials(text)
    assert "$1$EEar$abc" not in redacted
    assert "$9$xyz" not in redacted
    assert "cleartext" not in redacted
    assert "<<REDACTED:credential:" in redacted
    assert mapping["<<REDACTED:credential:1>>"] == "<SUPPRESSED>"

def test_line_vty_redaction():
    text = "line vty 0 4\n password 7 08701E1D5D\n login local"
    redacted, _ = suppress_credentials(text)
    assert "08701E1D5D" not in redacted
    assert "<<REDACTED:credential:1>>" in redacted

def test_snmp_v2_v3_redaction():
    text = "snmp-server community s3cr3t RO\nsnmp-server user netmon Monitoring v3 auth sha MyAuthK3y priv aes 256 MyPrivK3y"
    redacted, _ = suppress_credentials(text)
    assert "s3cr3t" not in redacted
    assert "MyAuthK3y" not in redacted
    assert "MyPrivK3y" not in redacted
    assert redacted.count("<<REDACTED:credential:") == 3

def test_vpn_isakmp_ikev2_redaction():
    text = "crypto isakmp key P@ssw0rd address 203.0.113.1\npre-shared-key local LocalK3y\npre-shared-key remote RemoteK3y"
    redacted, _ = suppress_credentials(text)
    assert "P@ssw0rd" not in redacted
    assert "LocalK3y" not in redacted
    assert "RemoteK3y" not in redacted
    assert redacted.count("<<REDACTED:credential:") == 3

def test_routing_protocol_redaction():
    text = "neighbor 10.0.0.1 password MyBgpSecret\nip ospf authentication-key Router0spf\nip ospf message-digest-key 1 md5 0spfMd5K3y\nmpls ldp neighbor 1.1.1.1 password LdpPass"
    redacted, _ = suppress_credentials(text)
    assert "MyBgpSecret" not in redacted
    assert "Router0spf" not in redacted
    assert "0spfMd5K3y" not in redacted
    assert "LdpPass" not in redacted

def test_aaa_hsrp_vrrp_ntp_redaction():
    text = "radius-server key R4diusK3y\ntacacs-server key T4cacsK3y\nstandby 1 authentication md5 key-string MyHsrpMd5\nvrrp 1 authentication text MyVrrpText\nntp authentication-key 1 md5 NtpSecret"
    redacted, _ = suppress_credentials(text)
    assert "R4diusK3y" not in redacted
    assert "T4cacsK3y" not in redacted
    assert "MyHsrpMd5" not in redacted
    assert "MyVrrpText" not in redacted
    assert "NtpSecret" not in redacted

def test_ppp_wireless_keychain_redaction():
    text = "ppp chap password ChapP4ss\nwpa-psk ascii 2 MyWifiPass\nkey-string ChainedK3y"
    redacted, _ = suppress_credentials(text)
    assert "ChapP4ss" not in redacted
    assert "MyWifiPass" not in redacted
    assert "ChainedK3y" not in redacted

def test_juniper_redaction():
    text = 'secret "$9$abc123..."\npre-shared-key ascii-text "MyIkeKey"\nauthentication-key "BGPauth"'
    redacted, _ = suppress_credentials(text)
    assert "$9$abc123..." not in redacted
    assert "MyIkeKey" not in redacted
    assert "BGPauth" not in redacted

def test_pki_cert_chain_redaction():
    # Note: added \n before crypto to ensure ^ matches if needed, but here we just test internal match
    text = "crypto pki certificate chain TP-self-signed-1234\n certificate 308203E5...\n quit\nsome other config"
    redacted, _ = suppress_credentials(text)
    assert "certificate 308203E5" not in redacted
    assert "<<REDACTED:credential:1>>" in redacted
    assert "some other config" in redacted

def test_generic_redaction():
    text = "password: hunter2\napi-key: sk-abcdef\ntoken: ghp_xxx\npassphrase: 'my secret phrase'\nSECRET_KEY=abcdefgh1234\nDB_PASSWORD=s3cur3pass"
    redacted, _ = suppress_credentials(text)
    assert "hunter2" not in redacted
    assert "sk-abcdef" not in redacted
    assert "ghp_xxx" not in redacted
    assert "my secret phrase" not in redacted
    assert "abcdefgh1234" not in redacted
    assert "s3cur3pass" not in redacted

def test_multivendor_redaction():
    text = (
        "password cipher %@%@abc123%@%@\n"                        # Huawei
        "set password MyFortiPass\n"                              # Fortinet
        "<password>PaloPass</password>\n"                        # Palo Alto
        "    passphrase MyBigIpPassphrase\n"                     # F5
        "password manager managerHash\n"                         # HP/Aruba
        "authentication-key MyOspfKey\n"                         # Nokia
        "enable super-user-password Br0cadePass\n"               # Brocade
        "create account admin netadmin Extr3m3Pass\n"            # Extreme
        "/ip ipsec peer set [find name=peer1] secret=MikroTikKey\n" # MikroTik
        "radius-secret=RadiusK3y"                                 # MikroTik/Generic
    )
    redacted, _ = suppress_credentials(text)
    assert "abc123" not in redacted
    assert "MyFortiPass" not in redacted
    assert "PaloPass" not in redacted
    assert "MyBigIpPassphrase" not in redacted
    assert "managerHash" not in redacted
    assert "MyOspfKey" not in redacted
    assert "Br0cadePass" not in redacted
    assert "Extr3m3Pass" not in redacted
    assert "MikroTikKey" not in redacted
    assert "RadiusK3y" not in redacted
    # Ensure they are all redacted
    assert redacted.count("<<REDACTED:credential:") >= 10

def test_no_false_positives():
    text = (
        "interface GigabitEthernet0/0\n"
        " ip address 10.1.1.1 255.255.255.0\n"
        " key 1\n"
        " logging level debug\n"
        " password encryption aes\n"
        " set session-ttl 3600\n"             # Fortinet non-secret keyword
        " password: true\n"                   # Generic skip-list: boolean value
        " password: none\n"                   # Generic skip-list: none value
    )
    redacted, _ = suppress_credentials(text)
    # Most of this should NOT be redacted. 
    # 'password: true' and 'password: none' should be skipped by the suppress-skiplist
    assert "ip address 10.1.1.1" in redacted
    assert "key 1" in redacted
    assert "logging level debug" in redacted
    assert "password encryption aes" in redacted
    assert "set session-ttl 3600" in redacted
    assert "password: true" in redacted
    assert "password: none" in redacted

def test_middleware_human_message():
    mw = NetCredentialSuppressorMiddleware()
    state = {"messages": [HumanMessage(content="My password: hunter2")]}
    updates = mw.before_model(state, None)
    assert updates is not None
    assert "hunter2" not in updates["messages"][0].content
    assert updates["_net_cred_suppressed_map"]["<<REDACTED:credential:1>>"] == "<SUPPRESSED>"

def test_middleware_ai_message():
    mw = NetCredentialSuppressorMiddleware()
    state = {"messages": [AIMessage(content="Setting password: secret123")], "_net_cred_suppressed_map": {}}
    updates = mw.after_model(state, None)
    assert updates is not None
    assert "secret123" not in updates["messages"][0].content
    assert updates["_net_cred_suppressed_map"]["<<REDACTED:credential:1>>"] == "<SUPPRESSED>"

def test_middleware_tool_message():
    mw = NetCredentialSuppressorMiddleware(apply_to_tool_results=True)
    # Simulate a tool returning a Cisco config with a secret
    tool_content = "username admin secret 5 $1$abc123\ninterface Gi0/1\n password 7 08701E1D5D"
    state = {"messages": [ToolMessage(content=tool_content, tool_call_id="call_123")]}
    updates = mw.before_model(state, None)
    assert updates is not None
    redacted_msg = updates["messages"][0]
    assert "$1$abc123" not in redacted_msg.content
    assert "08701E1D5D" not in redacted_msg.content
    assert "<<REDACTED:credential:" in redacted_msg.content
    assert isinstance(redacted_msg, ToolMessage)
    assert redacted_msg.tool_call_id == "call_123"

def test_middleware_disable_tool_results():
    mw = NetCredentialSuppressorMiddleware(apply_to_tool_results=False)
    tool_content = "username admin secret 5 $1$abc123"
    state = {"messages": [ToolMessage(content=tool_content, tool_call_id="call_123")]}
    updates = mw.before_model(state, None)
    assert updates is None # No modification means it returns None

def test_middleware_disable_input():
    mw = NetCredentialSuppressorMiddleware(apply_to_input=False)
    state = {"messages": [HumanMessage(content="My password is hunter2")]}
    updates = mw.before_model(state, None)
    assert updates is None

def test_middleware_disable_output():
    mw = NetCredentialSuppressorMiddleware(apply_to_ai_output=False)
    state = {"messages": [AIMessage(content="Setting password: secret123")]}
    updates = mw.after_model(state, None)
    assert updates is None
