# Author: XTofTech
# Date: 2025-06-19

#1. mocks network operations
#2. runs a MCP server exposing those operations as tools
from typing import List
from mcp.server.fastmcp import FastMCP
import json
import paramiko
import re
from service_now_incidents_helper import ServiceNowIncident, instance_url, snow_api_key

mcp = FastMCP("network_tools_server")


class DeviceSShSession:
    def __init__(self, management_ip: str, username: str = 'admin', password: str = 'password'):
        self.management_ip = management_ip
        self.username = username
        self.password = password

    def execute_command(self, command: str) -> str:
        # create ssh connection to the device and execute the command, set timeout to 5 seconds, and change buffer to 15000
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.management_ip, username=self.username, password=self.password, timeout=5)
            stdin, stdout, stderr = ssh.exec_command(command)
            output = stdout.read(15000).decode()
            ssh.close()
            return output
        except Exception as e:
            return f"Error executing command: {e}"


        

@mcp.tool()
async def get_devices_management_ip(site_name:str, device_type:str) -> str:
    """Get management IP of a network device from a site, uses infor from CMDB, IPAM and NMS to get the info
    args:
        site_name (str): name of the site stripped of anything like office, building, floor etc.
        device_type (str): type of the device (e.g., switch, router)
    returns:
        str: management IP address of the device
    """
    print("**"*20)
    print(f"Getting management IP for device type {device_type} in site {site_name}")
    try:
        with open("sites.json", "r") as f:
            data = json.load(f)
        for site in data["sites"]:
            if site_name in site["name"]:
                for device in site["devices"]:
                    if device["type"].lower() == device_type.lower():
                        return device["management_ip"]
        # return only sites names so that AI checks if the site was not mispelled
        # filter sites names from data 
        print(f"{site_name} is not found in sites container.")
        sites_names = [site["name"] for site in data["sites"]]
        return f"Device management IP cannot be found, you could have issues wrong site name, try again. Available sites are: {', '.join(sites_names)}"
    except Exception as e:
        print(f"Error reading sites container: {e}")
    return "Device management IP cannot be found."

@mcp.tool()
async def find_network_interfaces(device_management_ip: str) -> str:
    """connect to the device management IP and Find network interfaces"""
    device = DeviceSShSession(device_management_ip)
    interfaces = device.execute_command("show ip interfaces brief | exclude unassigned")
    return interfaces

@mcp.tool()
async def ping_device_from_gateway(device_ip:str, target_ip: str, count: int =5) -> str:
    """Ping a device from a switch"""
    return f"Pinged {target_ip} {count} times failed."

@mcp.tool()
async def get_network_device_arp_table(device_management_ip: str) -> List[str]:
    """Get ARP table from a device"""
    device = DeviceSShSession(device_management_ip)
    arp_table = device.execute_command("show ip arp")
    return [line for line in arp_table.splitlines("\n") if line.strip()]

@mcp.tool()
async def get_switch_mac_address_table(device_management_ip: str) -> List[str]:
    """Get MAC address table from a device"""
    device = DeviceSShSession(device_management_ip)
    mac_table = device.execute_command("show mac address-table")
    return [line for line in mac_table.splitlines("\n") if line.strip()]

@mcp.tool()
async def get_l2_forwarding_information(device_management_ip: str) -> str:
    """Get trunking status and spanning tree information from the switch
    args:
        device_management_ip (str): management IP of the switch
    """
    try:
        device = DeviceSShSession(device_management_ip)
        # retrieve trunking and spanning tree info via ssh command
        trunking_info = device.execute_command("show interfaces trunk")
        spanning_tree_info = device.execute_command("show spanning-tree")
    except Exception as e:
        return f"Error retrieving L2 information: {e}"
    return f"Trunking Info:\n{trunking_info}\nSpanning Tree Info:\n{spanning_tree_info}"
    

@mcp.tool()
async def get_nat_table(router_management_ip: str) -> List[str]:
    """Get NAT table from a router
    params:
        router_management_ip (str): management IP of the router
    """
    device = DeviceSShSession(router_management_ip)
    nat_table = device.execute_command("show ip nat translations")
    return [line for line in nat_table.splitlines("\n") if line.strip()]

@mcp.tool()
async def get_routing_table(router_management_ip: str) -> str:
    """Get routing table from a router"""
    device = DeviceSShSession(router_management_ip)
    routing_table = device.execute_command("show ip route")
    return f"routing table for router {router_management_ip}:\n{routing_table.splitlines("\n")}"

@mcp.tool()
async def capture_network_traffic(device_management_ip:str, interface: str, duration_seconds: int) -> str:
    """Capture network traffic on a given interface for a specified duration"""
    # returns a filtered pickup file
    captured_network_traffic = "No captured traffic"
    device = DeviceSShSession(device_management_ip)
    if device_model := device.execute_command("show version | include Model number"):
        print(f"Device model is {device_model}")
    if "cisco" in device_model.lower():

        commands = [
            "monitor capture buffer AI_CAPTURE size 10000",
            f"monitor capture AI_CAPTURE {interface} both",
            "monitor capture AI_CAPTURE match ipv4 protocol tcp any any limit pps 1000000",
            "monitor capture start AI_CAPTURE",
        ]
        for command in commands:
            device.execute_command(command)
        # wait for duration_seconds
        import time
        time.sleep(duration_seconds)
        # stop capture
        device.execute_command("monitor capture stop AI_CAPTURE")
        # show capture and export to tftp server (assuming tftp server is at TODO: to add this later)
        device.execute_command("term length 0")
        captured_network_traffic = device.execute_command("show monitor capture AI_CAPTURE buffer detailed")
        # if captured packets exist then sanitize the capture and filter what you look for using the tcpdump tool return the filtered capture
        # TODO: implement a cisco capture to pcap converter then apply it to the traffic and make it into text for LLM
    else:
        # TODO: implement for juniper, arista, palo alto, etc.
        print(f"Device model {device_model} not supported for traffic capture yet.")
    return f"Captured traffic on {interface} for {duration_seconds} seconds. is {captured_network_traffic}"

@mcp.tool()
async def get_device_logs(device_management_ip: str, log_type: str, time_range: str, filter_regex: str = "") -> List[str]:
    """Get device logs of a specific type within a time range
    args:
        device_management_ip (str): management IP of the device
        log_type (str): type of logs to retrieve (e.g., error, warning, info)
        time_range (str): time range for the logs (e.g., last 1 hour, last 24 hours)
        filter_regex Optional[str]: optional regex or keyword to filter logs
    """
    device = DeviceSShSession(device_management_ip)
    # retrieve logs via ssh command
    if log_type.lower() == "error":
        log_level = "-4-.*"
    elif log_type.lower() == "warning":
        log_level = "-5-.*"
    elif log_type.lower() == "info":
        log_level = "-6-.*"
    else:
        log_level = ".*"
    device_logs = device.execute_command(f"show logging | i {log_level}")
    # filter using regex the logs matching the time range 
    if time_range:
        time_range_expression = f"{time_range}.*"
        time_range_regexp = re.compile(time_range_expression)
        device_logs = [log for log in device_logs.splitlines("\n") if time_range_regexp.search(log)]
    else:
        device_logs = device_logs.splitlines("\n")
    return device_logs[:10]  # return first 10 logs for brevity

@mcp.tool()
async def run_command_on_device(device_management_ip: str, commands: List[str]) -> str:
    """Run a command on a network device via SSH
    args:
        device_management_ip (str): management IP of the device
        command (List[str]): list of commands to execute on the device
    returns:
        str: output of the command execution
    """
    device = DeviceSShSession(device_management_ip)
    output = ""
    for command in commands:
        _output = device.execute_command(command)
        output += f"Command: {command}\nOutput: {_output}\n"
    return output

@mcp.tool()
async def get_servicenow_incidents_by_priority(priority: int) -> str:
    """Get active ServiceNow incidents by priority
    args:
        priority (int): priority of the incidents to retrieve (1=Critical, 2=High, 3=Moderate, 4=Low, 5=Planning)
    returns:
        str: summary of active incidents with the specified priority
    """
    SERVICENOW_INSTANCE = instance_url
    ACCESS_TOKEN = snow_api_key
    
    # Create ServiceNow client
    sn_client = ServiceNowIncident(SERVICENOW_INSTANCE, ACCESS_TOKEN)
    
    result = sn_client.get_active_incidents(priority=priority)
    
    if result['success']:
        incidents = result['data']['result']
        summary = f"Retrieved {result['count']} active incidents with priority {priority}:\n"
        for inc in incidents:
            summary += f"- Number: {inc.get('number')}, Short Description: {inc.get('short_description')}\n"
        return summary
    else:
        return f"Error retrieving incidents: {result['error']}"

@mcp.tool()
async def get_servicenow_incidents_by_incident_id(incident_id: str) -> str:
    """Get ServiceNow incident details by incident ID
    args:
        incident_id (str): incident number to retrieve
    returns:
        str: details of the specified incident
    """
    SERVICENOW_INSTANCE = instance_url
    ACCESS_TOKEN = snow_api_key
    
    # Create ServiceNow client
    sn_client = ServiceNowIncident(SERVICENOW_INSTANCE, ACCESS_TOKEN)
    # get all incidents and filter incidents where 
    result = sn_client.get_incidents()
    
    if result['success']:
        incident = result['data']
        details = f"Incident Details:\nNumber: {incident.get('number')}\nShort Description: {incident.get('short_description')}\nState: {incident.get('state')}\nPriority: {incident.get('priority')}\n"
        return details
    else:
        return f"Error retrieving incident: {result['error']}"
    
@mcp.tool()
async def get_servicenow_incident_by_user(user: str) -> str:
    """Get ServiceNow incidents assigned to a specific user
    args:
        user (str): a user like peter torch ...
    returns:
        str: summary of incidents assigned to the user
    """
    SERVICENOW_INSTANCE = instance_url
    ACCESS_TOKEN = snow_api_key
    
    # Create ServiceNow client
    sn_client = ServiceNowIncident(SERVICENOW_INSTANCE, ACCESS_TOKEN)
    
    result = sn_client.get_my_incidents(user)
    
    if result['success']:
        incidents = result['data']['result']
        summary = f"Retrieved {result['count']} incidents assigned to user {user}:\n"
        for inc in incidents:
            summary += f"- Number: {inc.get('number')}, Short Description: {inc.get('short_description')}\n"
        return summary
    else:
        return f"Error retrieving incidents: {result['error']}"

@mcp.tool()
async def cloud_ssh_tool(management_ip: str, cloud_provider: str, username: str, password: str, command: List[str]) -> str:
    """SSH into a cloud VM and run a command, it can run commands on AWS, Azure, GCP
    args:
        management_ip (str): management IP of the VM
        cloud_provider (str): the cloud provider (AWS, Azure, GCP)
        username (str): SSH username
        password (str): SSH password
        command (List[str]): commands to execute
    returns:
        str: output of the command execution
    """
    device = DeviceSShSession(management_ip, username, password)
    print(f"Connecting to {cloud_provider} VM at {management_ip} as {username}")
    output = ""
    for cmd in command:
        print(f"Executing command: {cmd}")
        _output = device.execute_command(cmd)
        output += f"Command: {cmd}\nOutput: {_output}\n"
    return output
    return output


if __name__ == "__main__":
    mcp.run(transport="streamable-http")