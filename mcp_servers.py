# Author: XTofTech
# Date: 2025-06-19

#1. mocks network operations
#2. runs a MCP server exposing those operations as tools
from typing import List, Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
import json
import paramiko
import re
import logging
import sys
from service_now_incidents_helper import ServiceNowIncident
from service_now_changes_helper import ServiceNowChangeRequest
from snow_creds import instance_url, snow_api_key
import subprocess
import tempfile
import os
import contextlib
import io
import asyncio
import traceback
import base64
import aiohttp
import urllib.parse
from pathlib import Path
import xml.etree.ElementTree as ET
import csv
from datetime import datetime
from tools_helpers.retriever_archiver import ArchiverRetriever
import creds
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

mcp = FastMCP("network_tools_server")

# Initialize Retriever Archiver
try:
    os.environ["OPENAI_API_KEY"] = creds.OPENAI_KEY
    archiver = ArchiverRetriever()
    logger.info("Retriever Archiver initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Retriever Archiver: {e}")
    archiver = None


def log_tool_call_to_csv(tool_name: str, intention: str, **kwargs):
    """Logs tool call details to a CSV file in ~/.net_deepagent/tool_calls_logger.csv"""
    try:
        log_dir = os.path.expanduser("~/.net_deepagent")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "tool_calls_logger.csv")
        
        file_exists = os.path.isfile(log_file)
        with open(log_file, mode='a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'tool_name', 'arguments', 'intention'])
            
            timestamp = datetime.now().isoformat()
            # Serialize arguments to JSON string to keep it in one CSV cell
            arguments_json = json.dumps(kwargs)
            writer.writerow([timestamp, tool_name, arguments_json, intention])
    except Exception as e:
        logger.error(f"Error logging tool call to CSV: {e}")


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
            if not "\n" in command:
                command += " \n"
            if not "?" in command:
                ssh.exec_command("terminal length 0\n")
                stdin, stdout, stderr = ssh.exec_command(command)
                time.sleep(0.5)
                output = stdout.read(15000).decode()
            else:
                shell = ssh.invoke_shell()
                time.sleep(1)

                # Clear initial banner
                if shell.recv_ready():
                    print(shell.recv(65535).decode())
                # Send command with ?
                shell.send(command)
                time.sleep(1)

                output = ""
                while shell.recv_ready():
                    output += shell.recv(65535).decode()
            ssh.close()
            return output
        except Exception as e:
            return f"Error executing command: {e}"
    
    def execute_privileged_command(self, command: str) -> str:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.management_ip, username=self.username, password=self.password, timeout=5)
            if not "\n" in command:
                command += " \n"
            if not "?" in command:
                ssh.exec_command("terminal length 0\n")
                time.sleep(0.5)
                ssh.exec_command("enable\n")
                time.sleep(0.5)
                stdin, stdout, stderr = ssh.exec_command(command)
                output = stdout.read(15000).decode()
            else:
                shell = ssh.invoke_shell()
                time.sleep(1)

                # Clear initial banner
                if shell.recv_ready():
                    print(shell.recv(65535).decode())
                # Send command with ?
                shell.send("enable\n")
                time.sleep(0.5)
                shell.send(command)
                time.sleep(1)

                output = ""
                while shell.recv_ready():
                    output += shell.recv(65535).decode()
            
            ssh.close()
            return output
        except Exception as e:
            return f"Error executing command: {e}"


        
@mcp.tool()
async def get_site_info(site_name: str, intention: str) -> str:
    """Get site information or site inventory. This is information about site details, such as devices
    name and IP address as well as site location and other details.
    args:
        site_name (str): name of the site
        intention (str): llm intention to call this tool
    returns:
        str: site information
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(get_site_info.__name__, intention, site_name=site_name)
    logger.info(f"Getting site info for site: {site_name}")
    with open("sites.json", "r") as f:
        data = json.load(f)
    for site in data["sites"]:
        if site_name.lower() in site["name"].lower():
            return json.dumps(site, indent=2)
    return f"Site {site_name} not found"

@mcp.tool()
async def net_get_devices_management_ip(site_name: str, device_type: str, intention: str) -> str:
    """Get management IP of a network device from a site, uses infor from CMDB, IPAM and NMS to get the info
    args:
        site_name (str): name of the site stripped of anything like office, building, floor etc.
        device_type (str): type of the device (e.g., switch, router)
        intention (str): llm intention to call this tool
    returns:
        str: management IP address of the device
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_get_devices_management_ip.__name__, intention, site_name=site_name, device_type=device_type)
    logger.info(f"Getting management IP for device type {device_type} in site {site_name}")
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
        logger.warning(f"{site_name} is not found in sites container.")
        sites_names = [site["name"] for site in data["sites"]]
        return f"Device management IP cannot be found, you could have issues wrong site name, try again. Available sites are: {', '.join(sites_names)}"
    except Exception as e:
        logger.error(f"Error reading sites container: {e}")
    return "Device management IP cannot be found."

@mcp.tool()
async def net_find_network_interfaces(device_management_ip: str, intention: str) -> str:
    """connect to the device management IP and Find network interfaces
    args:
        device_management_ip (str): management IP of the device
        intention (str): llm intention to call this tool
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_find_network_interfaces.__name__, intention, device_management_ip=device_management_ip)
    logger.info(f"Finding network interfaces for device: {device_management_ip}")
    device = DeviceSShSession(device_management_ip)
    interfaces_with_ip = device.execute_command("show ip interfaces brief | exclude unassigned")
    interface_physical = device.execute_command("show interface status")
    return interfaces_with_ip + "\n" + interface_physical

#@mcp.tool()
#async def net_ping_device_from_gateway(device_ip: str, target_ip: str, intention: str, count: int = 5) -> str:
#    """Ping a device from a switch or router where the device is connected to.
#    Mainly used in environments with VPN or device is behind NAT.
#    This is used if the device IP address we want to reach is on different subnet than the current machinewe are on.
#    Run shell tool to know our current machine IP.
#    # NOTE: not implemented at the moment as it requires more scrutiny on how it works
#    args:
#        device_ip (str): IP of the device
#        target_ip (str): target IP to ping
#        intention (str): llm intention to call this tool
#        count (int): number of pings (default: 5)
#    """
#    logger.info(f"Intention: {intention}")
#    log_tool_call_to_csv("ping_device_from_gateway", intention, device_ip=device_ip, target_ip=target_ip, count=count)
#    logger.info(f"Pinging {target_ip} from {device_ip} (count={count})")
#    return f"Pinged {target_ip} {count} times failed."

@mcp.tool()
async def net_get_network_device_arp_table(device_management_ip: str, intention: str) -> List[str]:
    """Get ARP table from a device
    args:
        device_management_ip (str): management IP of the device
        intention (str): llm intention to call this tool
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_get_network_device_arp_table.__name__, intention, device_management_ip=device_management_ip)
    logger.info(f"Getting ARP table for device: {device_management_ip}")
    device = DeviceSShSession(device_management_ip)
    arp_table = device.execute_command("show ip arp")
    return [line for line in arp_table.splitlines("\n") if line.strip()]

@mcp.tool()
async def net_get_switch_mac_address_table(device_management_ip: str, intention: str) -> List[str]:
    """Get MAC address table from a device
    args:
        device_management_ip (str): management IP of the device
        intention (str): llm intention to call this tool
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_get_switch_mac_address_table.__name__, intention, device_management_ip=device_management_ip)
    logger.info(f"Getting MAC address table for device: {device_management_ip}")
    device = DeviceSShSession(device_management_ip)
    mac_table = device.execute_command("show mac address-table")
    return [line for line in mac_table.splitlines("\n") if line.strip()]

@mcp.tool()
async def net_get_l2_forwarding_information(device_management_ip: str, intention: str) -> str:
    """Get trunking status and spanning tree information from the switch
    args:
        device_management_ip (str): management IP of the switch
        intention (str): llm intention to call this tool
    """
    try:
        logger.info(f"Intention: {intention}")
        log_tool_call_to_csv(net_get_l2_forwarding_information.__name__, intention, device_management_ip=device_management_ip)
        logger.info(f"Getting L2 forwarding info for device: {device_management_ip}")
        device = DeviceSShSession(device_management_ip)
        # retrieve trunking and spanning tree info via ssh command
        trunking_info = device.execute_command("show interfaces trunk")
        spanning_tree_info = device.execute_command("show spanning-tree")
    except Exception as e:
        return f"Error retrieving L2 information: {e}"
    return f"Trunking Info:\n{trunking_info}\nSpanning Tree Info:\n{spanning_tree_info}"
    

@mcp.tool()
async def net_get_nat_table(router_management_ip: str, intention: str) -> List[str]:
    """Get NAT table from a router
    args:
        router_management_ip (str): management IP of the router
        intention (str): llm intention to call this tool
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_get_nat_table.__name__, intention, router_management_ip=router_management_ip)
    logger.info(f"Getting NAT table for router: {router_management_ip}")
    device = DeviceSShSession(router_management_ip)
    nat_table = device.execute_command("show ip nat translations")
    return [line for line in nat_table.splitlines("\n") if line.strip()]

@mcp.tool()
async def net_get_routing_table(router_management_ip: str, intention: str) -> str:
    """Get routing table from a router
    args:
        router_management_ip (str): management IP of the router
        intention (str): llm intention to call this tool
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_get_routing_table.__name__, intention, router_management_ip=router_management_ip)
    logger.info(f"Getting routing table for router: {router_management_ip}")
    device = DeviceSShSession(router_management_ip)
    routing_table = device.execute_command("show ip route")
    return f"routing table for router {router_management_ip}:\n{routing_table.splitlines("\n")}"

@mcp.tool()
async def net_capture_network_traffic(device_management_ip: str, interface: str, duration_seconds: int, intention: str) -> str:
    """Capture network traffic on a given interface for a specified duration
    args:
        device_management_ip (str): management IP of the device
        interface (str): interface to capture traffic on
        duration_seconds (int): duration of capture in seconds
        intention (str): llm intention to call this tool
    """
    # returns a filtered pickup file
    captured_network_traffic = "No captured traffic"
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_capture_network_traffic.__name__, intention, device_management_ip=device_management_ip, interface=interface, duration_seconds=duration_seconds)
    logger.info(f"Capturing network traffic on {device_management_ip} interface {interface} for {duration_seconds}s")
    device = DeviceSShSession(device_management_ip)
    if device_model := device.execute_command("show version | include Model number"):
        logger.info(f"Device model is {device_model}")
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
        logger.warning(f"Device model {device_model} not supported for traffic capture yet.")
    return f"Captured traffic on {interface} for {duration_seconds} seconds. is {captured_network_traffic}"

@mcp.tool()
async def net_get_device_logs(device_management_ip: str, log_type: str, time_range: str, intention: str, filter_regex: str = "") -> List[str]:
    """Get device logs of a specific type within a time range
    args:
        device_management_ip (str): management IP of the device
        log_type (str): type of logs to retrieve (e.g., error, warning, info)
        time_range (str): time range for the logs (e.g., last 1 hour, last 24 hours)
        intention (str): llm intention to call this tool
        filter_regex Optional[str]: optional regex or keyword to filter logs
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_get_device_logs.__name__, intention, device_management_ip=device_management_ip, log_type=log_type, time_range=time_range, filter_regex=filter_regex)
    logger.info(f"Getting device logs for {device_management_ip} (type={log_type}, range={time_range})")
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
async def net_run_commands_on_device(device_management_ip: str, commands: List[str], intention: str, privileged: bool = False) -> str:
    """Run a command on a network device via SSH
    args:
        device_management_ip (str): management IP of the device
        commands (List[str]): list of commands to execute on the device
        intention (str): llm intention to call this tool
        privileged (bool): whether to run the command in privileged mode
    returns:
        str: output of the command execution
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_run_commands_on_device.__name__, intention, device_management_ip=device_management_ip, commands=commands)
    logger.info(f"Running commands on {device_management_ip}: {commands}")
    device = DeviceSShSession(device_management_ip)
    output = ""
    if privileged:
        for command in commands:
            _output = device.execute_privileged_command(command)
            output += f"Command: {command}\nOutput: {_output}\n"
    else:
        for command in commands:
            _output = device.execute_command(command)
            output += f"Command: {command}\nOutput: {_output}\n"
    return output

@mcp.tool()
async def servicenow_get_incidents_by_priority(priority: int, intention: str) -> str:
    """Get active ServiceNow incidents by priority
    args:
        priority (int): priority of the incidents to retrieve (1=Critical, 2=High, 3=Moderate, 4=Low, 5=Planning)
        intention (str): llm intention to call this tool
    returns:
        str: summary of active incidents with the specified priority
    """
    SERVICENOW_INSTANCE = instance_url
    ACCESS_TOKEN = snow_api_key
    
    # Create ServiceNow client
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(servicenow_get_incidents_by_priority.__name__, intention, priority=priority)
    logger.info(f"Getting active ServiceNow incidents with priority {priority}")
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
async def servicenow_get_incidents_by_incident_id(incident_id: str, intention: str) -> str:
    """Get ServiceNow incident details by incident ID
    args:
        incident_id (str): incident number to retrieve
        intention (str): llm intention to call this tool
    returns:
        str: details of the specified incident
    """
    SERVICENOW_INSTANCE = instance_url
    ACCESS_TOKEN = snow_api_key
    
    # Create ServiceNow client
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(servicenow_get_incidents_by_incident_id.__name__, intention, incident_id=incident_id)
    logger.info(f"Getting ServiceNow incident details for ID: {incident_id}")
    sn_client = ServiceNowIncident(SERVICENOW_INSTANCE, ACCESS_TOKEN)
    # get all incidents and filter incidents where 
    result = sn_client.get_incident_by_id(incident_id)
    
    if result['success']:
        # get_incident_by_id returns {'result': {...}} so result['data']['result'] is the object
        incident = result['data'].get('result', {})
        details = f"Incident Details:\nNumber: {incident.get('number')}\nShort Description: {incident.get('short_description')}\nState: {incident.get('state')}\nPriority: {incident.get('priority')}\n"
        return details
    else:
        return f"Error retrieving incident: {result['error']}"
    
@mcp.tool()
async def servicenow_get_incidents_by_user(user: str, intention: str) -> str:
    """Get ServiceNow incidents assigned to a specific user
    args:
        user (str): a user like peter torch ...
        intention (str): llm intention to call this tool
    returns:
        str: summary of incidents assigned to the user
    """
    SERVICENOW_INSTANCE = instance_url
    ACCESS_TOKEN = snow_api_key
    
    # Create ServiceNow client
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(servicenow_get_incidents_by_user.__name__, intention, user=user)
    logger.info(f"Getting ServiceNow incidents for user: {user}")
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
async def servicenow_get_unassigned_incidents_for_group(group_name: str, intention: str) -> str:
    """Get unassigned ServiceNow incidents for a specific group
    args:
        group_name (str): The name of the group (e.g., 'Software')
        intention (str): llm intention to call this tool
    returns:
        str: summary of unassigned incidents for the group
    """
    SERVICENOW_INSTANCE = instance_url
    ACCESS_TOKEN = snow_api_key
    
    # Create ServiceNow client
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(servicenow_get_unassigned_incidents_for_group.__name__, intention, group_name=group_name)
    logger.info(f"Getting unassigned incidents for group: {group_name}")
    sn_client = ServiceNowIncident(SERVICENOW_INSTANCE, ACCESS_TOKEN)
    
    result = sn_client.get_unassigned_group_incidents(group_name)
    
    if result['success']:
        incidents = result['data']['result']
        count = result['count']
        if count == 0:
            return f"No unassigned incidents found for group '{group_name}'."
            
        summary = f"Retrieved {count} unassigned incidents for group '{group_name}':\n"
        for inc in incidents:
            summary += f"- Number: {inc.get('number')}, Short Description: {inc.get('short_description')}\n"
        return summary
    else:
        return f"Error retrieving unassigned incidents: {result.get('error', 'Unknown error')}"

@mcp.tool()
async def servicenow_create_incident(short_description: str, intention: str, description: str = '', caller_id: str = '', urgency: int = 3, impact: int = 3, assignment_group: str = '') -> str:
    """Create a new  incident in ServiceNow
    args:
        short_description (str): Brief summary of the issue
        intention (str): llm intention to call this tool
        description (str): Detailed description (optional)
        caller_id (str): Name or sys_id of the person reporting (optional)
        urgency (int): 1 (Critical), 2 (High), 3 (Moderate), 4 (Low) (default: 3)
        impact (int): 1 (High), 2 (Medium), 3 (Low) (default: 3)
        assignment_group (str): Name or sys_id of the group to assign (optional)
    returns:
        str: summary of the created incident
    """
    SERVICENOW_INSTANCE = instance_url
    ACCESS_TOKEN = snow_api_key
    
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(servicenow_create_incident.__name__, intention, short_description=short_description, caller_id=caller_id, urgency=urgency, impact=impact, assignment_group=assignment_group)
    logger.info(f"Creating ServiceNow incident: {short_description}")
    
    sn_client = ServiceNowIncident(SERVICENOW_INSTANCE, ACCESS_TOKEN)
    
    result = sn_client.create_incident(
        short_description=short_description,
        description=description,
        caller_id=caller_id,
        urgency=urgency,
        impact=impact,
        assignment_group=assignment_group
    )
    
    if result['success']:
        incident_data = result['data']['result']
        return f"✅ Incident Created Successfully!\nNumber: {incident_data.get('number')}\nShort Description: {incident_data.get('short_description')}\nPriority: {incident_data.get('priority')}\nSys ID: {incident_data.get('sys_id')}"
    else:
        return f"❌ Failed to create incident: {result.get('error', 'Unknown error')}"

@mcp.tool()
async def servicenow_create_change_request(short_description: str, description: str, intention: str, priority: str = '4', risk: str = '3', impact: str = '3', ci_name: str = '') -> str:
    """Create a ServiceNow change request
    args:
        short_description (str): Short summary of the change
        description (str): Detailed description
        intention (str): llm intention to call this tool
        priority (str): Priority 1-5 (default: 4)
        risk (str): Risk 1-3 (default: 3)
        impact (str): Impact 1-3 (default: 3)
        ci_name (str): specific Config Item name (server, app, etc)
    returns:
        str: summary of the created change request
    """
    SERVICENOW_INSTANCE = instance_url
    ACCESS_TOKEN = snow_api_key
    
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(servicenow_create_change_request.__name__, intention, short_description=short_description, description=description, priority=priority, risk=risk, impact=impact, ci_name=ci_name)
    logger.info(f"Creating change request: {short_description}")
    sn_client = ServiceNowChangeRequest(SERVICENOW_INSTANCE, ACCESS_TOKEN)
    
    result = sn_client.create_change_request(
        short_description=short_description,
        description=description,
        priority=priority,
        risk=risk,
        impact=impact,
        cmdb_ci=ci_name
    )
    
    if result['success']:
        change_data = result['data']['result']
        return f"✅ Change Request Created Successfully!\nNumber: {change_data.get('number')}\nSys ID: {change_data.get('sys_id')}\nLink: {result['data']['result'].get('link', 'N/A')}"
    else:
        return f"❌ Failed to create change request: {result.get('error', 'Unknown error')}"

@mcp.tool()
async def cloud_ssh_tool(management_ip: str, cloud_provider: str, username: str, password: str, command: List[str], intention: str) -> str:
    """SSH into a cloud VM and run a command, it can run commands on AWS, Azure, GCP
    args:
        management_ip (str): management IP of the VM
        cloud_provider (str): the cloud provider (AWS, Azure, GCP)
        username (str): SSH username
        password (str): SSH password
        command (List[str]): commands to execute
        intention (str): llm intention to call this tool
    returns:
        str: output of the command execution
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(cloud_ssh_tool.__name__, intention, management_ip=management_ip, cloud_provider=cloud_provider, username=username, command=command)
    logger.info(f"Connecting to {cloud_provider} VM at {management_ip} as {username}")
    device = DeviceSShSession(management_ip, username, password)
    output = ""
    for cmd in command:
        logger.info(f"Executing command: {cmd}")
        _output = device.execute_command(cmd)
        output += f"Command: {cmd}\nOutput: {_output}\n"
    return output

@mcp.tool()
async def linux_server_ssh_tool(management_ip: str, command: List[str], intention: str, username: str = 'admin', password: str = 'password') -> str:
    """SSH into a Linux server and run a command
    args:
        management_ip (str): management IP of the VM
        command (List[str]): commands to execute
        intention (str): llm intention to call this tool
        username (str): SSH username (default: admin)
        password (str): SSH password (default: password)
    returns:
        str: output of the command execution
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(linux_server_ssh_tool.__name__, intention, management_ip=management_ip, command=command, username=username)
    logger.info(f"Connecting to Linux server at {management_ip} as {username}")
    device = DeviceSShSession(management_ip, username, password)
    output = ""
    for cmd in command:
        logger.info(f"Executing command: {cmd}")
        _output = device.execute_command(cmd)
        output += f"Command: {cmd}\nOutput: {_output}\n"
    return output

@mcp.tool()
async def execute_shell_command(command: str, intention: str, timeout: int = 60) -> str:
    """
    Execute a shell or bash command on the host machine in a safe manner.
    This can safely be used with AI agent with no risk of damaging the local machine.
    Use this for network diagnostics (ping, traceroute, dig, curl, tshark, netstatetc.) or other CLI tasks.
    sometime when tools are missing you may install them using apt-get or yum or dnf etc.
    
    Args:
        command (str): The shell command to execute.
        intention (str): llm intention to call this tool
        timeout (int): Timeout in seconds (default: 60).
        
    Returns:
        str: Combined stdout and stderr output.
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(execute_shell_command.__name__, intention, command=command, timeout=timeout)
    logger.info(f"Executing shell command: {command}")
    
    try:
        # Use asyncio.create_subprocess_shell for non-blocking execution
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            
            output = ""
            if stdout:
                output += stdout.decode().strip()
            if stderr:
                if output:
                    output += "\nSTDERR:\n"
                output += stderr.decode().strip()
                
            return_code = process.returncode
            if return_code != 0:
                output += f"\nCommand failed with return code {return_code}"
                
            return output
            
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            return f"Error: Command timed out after {timeout} seconds"
            
    except Exception as e:
        return f"Error executing command: {str(e)}"

@mcp.tool()
async def execute_generated_code(code: str, intention: str, mode: str = "docker", dependencies: List[str] = []) -> str:
    """
    Executes Python code generated by an LLM with options for local, sandboxed, or internal execution.

    Args:
        code (str): The Python code to execute.
        intention (str): llm intention to call this tool
        mode (str): The execution mode. options:
            - 'docker': (Default) Runs the code inside a 'python:3-slim' Docker container. (Recommended for safety).
            - 'local_process': Runs the code directly on the host system as a subprocess. (WARNING: Risky, uses system privileges).
            - 'internal': Runs the code using exec() inside the current process. (CRITICAL RISK: Can modify server state/crash server. Use only if interaction with other internal functions is required).
        dependencies (List[str]): A list of pip packages to install before execution (Docker mode only currently).

    Returns:
        str: The combined stdout/stderr output of the executed code, or error details.
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(execute_generated_code.__name__, intention, code=code, mode=mode, dependencies=dependencies)
    logger.info(f"Executing generated code. Mode: {mode}")
    
    # Clean up code string (remove markdown code blocks if present)
    code = code.strip()
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    
    output = ""
    
    try:
        if mode == "docker":
            # Safest mode
            # Create a localized temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_script:
                temp_script.write(code)
                temp_script_path = temp_script.name
            
            try:
                # Prepare docker command
                # We mount the temp file to /app/script.py
                # Note: This assumes docker is installed and user has permission
                volume_mount = f"{os.path.abspath(temp_script_path)}:/app/script.py"
                
                # Ensure the container can read the file
                os.chmod(temp_script_path, 0o644)

                docker_cmd = ["docker", "run", "--rm", "-v", volume_mount, "python:3-slim", "bash", "-c"]
                
                # Construct the shell command inside docker
                internal_cmds = []
                if dependencies:
                    internal_cmds.append(f"pip install {' '.join(dependencies)}")
                internal_cmds.append("python /app/script.py")
                
                full_shell_cmd = " && ".join(internal_cmds)
                docker_cmd.append(full_shell_cmd)
                
                logger.info(f"Running docker command: {docker_cmd}")
                
                result = subprocess.run(
                    docker_cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=120 
                )
                output = result.stdout + result.stderr
                
            finally:
                if os.path.exists(temp_script_path):
                    os.remove(temp_script_path)
                    
        elif mode == "local_process":
            # RISKY: Runs on host
            logger.warning("Executing code in 'local_process' mode. This is potentially unsafe.")
            if dependencies:
                logger.warning("Dependencies argument is ignored in local_process mode to avoid polluting system environment.")

            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_script:
                temp_script.write(code)
                temp_script_path = temp_script.name
            
            try:
                # Run the script
                result = subprocess.run(
                    [sys.executable, temp_script_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                output = result.stdout + result.stderr
            finally:
                if os.path.exists(temp_script_path):
                    os.remove(temp_script_path)

        

        else:
            return f"Error: Unknown execution mode '{mode}'"

    except subprocess.TimeoutExpired:
        output += "\nExecution timed out."
    except Exception as e:
        output += f"\nExecution failed: {str(e)}\n{traceback.format_exc()}"

    return output


@mcp.tool()
async def net_execute_with_tool_modification(
    tool_name: str,
    tool_params: dict,
    modification_code: str,
    intention: str
) -> str:
    """
    Executes an existing MCP tool and then modifies its output using provided Python code.
    
    This allows the LLM to chain tool calls with custom post-processing logic.
    
    Args:
        tool_name (str): The name of the MCP tool to execute (e.g., "read_file", "search_database").
        tool_params (dict): A dictionary of parameters to pass to the tool.
        modification_code (str): Python code to modify the output. The original output is available 
                                as 'original_output' variable. Set 'modified_output' variable with the result.
                                Example: "modified_output = original_output.upper()"
        intention (str): llm intention to call this tool
    
    Returns:
        str: The modified output from the tool, or error details if execution fails.
    
    Example:
        tool_name = "read_file"
        tool_params = {"path": "/data/report.txt"}
        modification_code = '''
import json
lines = original_output.split('\\n')
modified_output = json.dumps({"line_count": len(lines), "preview": lines[0]})
'''
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(net_execute_with_tool_modification.__name__, intention, tool_name=tool_name, tool_params=tool_params, modification_code=modification_code)
    logger.info(f"Executing tool '{tool_name}' with modification")
    
    try:
        # Get the tool function from the MCP server's registered tools
        tool_func = _get_tool_by_name(tool_name)
        
        if tool_func is None:
            return f"Error: Tool '{tool_name}' not found in registered MCP tools"
        
        # Execute the original tool
        logger.info(f"Calling tool '{tool_name}' with params: {tool_params}")
        original_output = await tool_func(**tool_params)
        
        # Convert to string if not already
        if not isinstance(original_output, str):
            original_output = str(original_output)
        
        # Clean up modification code (remove markdown if present)
        modification_code = modification_code.strip()
        if modification_code.startswith("```python"):
            modification_code = modification_code[9:]
        elif modification_code.startswith("```"):
            modification_code = modification_code[3:]
        if modification_code.endswith("```"):
            modification_code = modification_code[:-3]
        
        # Create execution context with original output
        local_vars = {
            "original_output": original_output,
            "modified_output": original_output  # Default to original if not set
        }
        
        # Execute modification code
        logger.info("Executing modification code")
        exec(modification_code, {"__builtins__": __builtins__}, local_vars)
        
        # Return the modified output
        result = local_vars.get("modified_output", original_output)
        
        # Ensure we return a string
        if not isinstance(result, str):
            result = str(result)
            
        logger.info("Tool modification completed successfully")
        return result
        
    except Exception as e:
        error_msg = f"Error executing tool with modification: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg


def _get_tool_by_name(tool_name: str):
    """
    Helper function to retrieve an MCP tool function by name.
    
    This implementation depends on how your MCP server registers tools.
    You may need to adjust this based on your specific MCP framework.
    
    Args:
        tool_name (str): The name of the tool to retrieve
        
    Returns:
        The tool function if found, None otherwise
    """
    # Option 1: If using mcp library with a registry
    # Adjust this based on your actual MCP implementation
    try:
        # Check if mcp has a tools registry
        if hasattr(mcp, 'tools'):
            return mcp.tools.get(tool_name)
        
        # Option 2: If tools are stored in a global registry
        if hasattr(mcp, '_tool_registry'):
            return mcp._tool_registry.get(tool_name)
        
        # Option 3: Search through globals for the decorated function
        # This assumes tools are defined in the same module
        for name, obj in globals().items():
            if callable(obj) and hasattr(obj, '__name__') and obj.__name__ == tool_name:
                return obj
        
        # Option 4: If you have a specific way tools are registered
        # Add your custom logic here
        
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving tool '{tool_name}': {str(e)}")
        return None

@mcp.tool()
async def get_skill_all_related_tools(skill_name: str, intention: str) -> str:
    """
    Get all related tools for a given skill
    args:
        skill_name (str): The name of the skill
        intention (str): llm intention to call this tool
    returns:
        str: a string with a tuple of (tool_name, tool_description) for each related tool
    """
    # get all current MCP tools then filter them according to the skill_name given
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(get_skill_all_related_tools.__name__, intention, skill_name=skill_name)
    # all skill related tools start with <skill-name>_name-of-the-tool
    # example: linux_server_ssh_tool for linux server skill
    # TODO: test if LLM is able to call such tools when they were not passed to LLM as part of the tools list
    all_tools = globals()
    skill_tools = [tool for tool in all_tools if tool.startswith(skill_name + "_")]
    # get tool name and description
    skill_tools = [(tool.__name__, tool.__doc__) for tool in skill_tools]
    logger.info(f"Skill tools information: {skill_tools}")
    return f"{skill_name} skill tools: {skill_tools}"

@mcp.tool()
async def visualize_drawio_diagram(
    diagram_xml_code: str,
    intention: str,
    save_to_file: Optional[str] = None,
    width: int = 800,
    height: int = 600,
    scale: float = 1.0,
    border: int = 0
) -> str:
    """
    Visualize a drawio diagram using Diagrams.net export API.
    NOTE: Do not use until proven working
    
    Args:
        diagram_xml_code (str): The XML code of the diagram
        intention (str): llm intention to call this tool
        save_to_file (Optional[str]): Path to save the PNG image
        width (int): Width of the image (default: 800)
        height (int): Height of the image (default: 600)
        scale (float): Scale factor (default: 1.0)
        border (int): Border width (default: 0)
        
    Returns:
        str: base64 encoded png image of the diagram
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(visualize_drawio_diagram.__name__, intention, diagram_xml_code=diagram_xml_code, save_to_file=save_to_file, width=width, height=height, scale=scale, border=border)
    logger.info("Visualizing draw.io diagram via export API")
    
    export_url = "https://convert.diagrams.net/node/export"
    
    async with aiohttp.ClientSession() as session:
        # We request binary data (base64=0) because we need it for saving to file
        params = {
            'format': 'png',
            'xml': diagram_xml_code,
            'bg': 'none',
            'base64': '0',
            'w': str(width),
            'h': str(height),
            'border': str(border),
            'scale': str(scale)
        }
        
        headers = {
            'Origin': 'https://app.diagrams.net',
            'Referer': 'https://app.diagrams.net/'
        }
        
        try:
            async with session.post(
                export_url,
                data=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_body = await response.text()
                    logger.error(f"Draw.io export failed: {response.status} - {error_body}")
                    return f"Error: Export failed with status {response.status} - {error_body}"
                
                image_bytes = await response.read()
                
                if not image_bytes:
                    logger.error("Received empty response from Draw.io API")
                    return "Error: Received empty response from API"
                
                # Save to file if requested
                if save_to_file:
                    save_path = Path(save_to_file)
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(save_path, 'wb') as f:
                        f.write(image_bytes)
                    logger.info(f"✓ PNG saved to: {save_path.absolute()}")
                
                base64_result = base64.b64encode(image_bytes).decode('utf-8')
                logger.info(f"Successfully visualized diagram. Base64 length: {len(base64_result)}")
                return base64_result
                
        except Exception as e:
            logger.error(f"Exception during draw.io visualization: {str(e)}")
            return f"Error: {str(e)}"

@mcp.tool()
async def analyze_drawio_diagram(diagram_xml: str, intention: str, original_request: str = "") -> str:
    """
    Performs a deep audit of a Draw.io XML diagram to identify 'bizarre' errors.
    Checks for overlapping nodes, missing connections, orphans, and alignment with the request.
    
    Args:
        diagram_xml (str): The raw Draw.io XML code.
        intention (str): llm intention to call this tool
        original_request (str): The initial user instruction to compare against.
        
    Returns:
        str: A Markdown formatted audit report.
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(analyze_drawio_diagram.__name__, intention, diagram_xml=diagram_xml, original_request=original_request)
    logger.info("Analyzing draw.io diagram logic")
    try:
        # 1. Parse XML
        # Handle cases where XML might be wrapped in <mxfile> or starts at <mxGraphModel>
        root = ET.fromstring(diagram_xml)
        
        nodes = {}
        edges = []
        
        # Find all mxCell elements
        for cell in root.iter('mxCell'):
            cell_id = cell.get('id')
            if not cell_id or cell_id in ('0', '1'):  # Skip root layers
                continue
                
            # Node (vertex)
            if cell.get('vertex') == '1':
                geometry = cell.find('mxGeometry')
                nodes[cell_id] = {
                    'id': cell_id,
                    'value': cell.get('value', '').replace('\n', ' '),
                    'x': float(geometry.get('x', 0)) if geometry is not None else 0,
                    'y': float(geometry.get('y', 0)) if geometry is not None else 0,
                    'w': float(geometry.get('width', 0)) if geometry is not None else 0,
                    'h': float(geometry.get('height', 0)) if geometry is not None else 0,
                    'connections': 0
                }
            
            # Edge (connection)
            elif cell.get('edge') == '1':
                edges.append({
                    'id': cell_id,
                    'source': cell.get('source'),
                    'target': cell.get('target'),
                    'value': cell.get('value', '')
                })
        
        # 2. Connection Analysis
        for edge in edges:
            if edge['source'] in nodes:
                nodes[edge['source']]['connections'] += 1
            if edge['target'] in nodes:
                nodes[edge['target']]['connections'] += 1
                
        # 3. Collision Detection (Overlaps)
        overlaps = []
        node_ids = list(nodes.keys())
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                n1 = nodes[node_ids[i]]
                n2 = nodes[node_ids[j]]
                
                # Check AABB collision
                if (n1['x'] < n2['x'] + n2['w'] and
                    n1['x'] + n1['w'] > n2['x'] and
                    n1['y'] < n2['y'] + n2['h'] and
                    n1['y'] + n1['h'] > n2['y']):
                    overlaps.append(f"• **Overlap**: '{n1['value']}' and '{n2['value']}' are physically colliding.")

        # 4. Logical Anomalies
        orphans = [n['value'] for n in nodes.values() if n['connections'] == 0 and n['value']]
        zero_size = [n['value'] for n in nodes.values() if (n['w'] <= 5 or n['h'] <= 5) and n['value']]

        # 5. Gap Analysis (Contextual Layer)
        gaps = []
        if original_request:
            req_lower = original_request.lower()
            
            # Categories of technology to check
            TECH_KEYWORDS = {
                "Routing Protocols": ["ospf", "bgp", "eigrp", "is-is", "rip", "static route"],
                "Overlay/Tunneling": ["mpls", "gre", "vxlan", "dmvpn", "ipsec", "vpn"],
                "Infrastructure": ["vlan", "subnet", "vrf", "stp", "lacp", "hsrp", "vrrp", "trunk"],
                "Security/Services": ["firewall", "load balancer", "f5", "nat", "acl"],
                "Device Types": ["router", "switch", "server", "pc", "laptop", "cloud", "aws", "azure"]
            }
            
            # Flatten diagram content for easy searching
            all_labels = " ".join([n['value'] for n in nodes.values()] + [e['value'] for e in edges]).lower()
            
            for category, keywords in TECH_KEYWORDS.items():
                for kw in keywords:
                    if kw in req_lower:
                        # Request mentioned this keyword, check if it exists in the diagram
                        if kw not in all_labels:
                            gaps.append(f"• **Missing {category}**: '{kw.upper()}' was requested but not found in any labels or links.")

        # 6. Generate Report
        report = ["### 📊 Diagram Audit Report"]
        
        if overlaps:
            report.append("\n#### ⚠️ Physical Issues (Bizarre Layout)")
            report.extend(overlaps)
        else:
            report.append("\n✅ **No physical overlaps detected.**")
            
        if orphans or zero_size:
            report.append("\n#### ❌ Logical Errors")
            if orphans:
                report.append(f"• **Orphan Nodes**: {', '.join(orphans)} have no connections.")
            if zero_size:
                report.append(f"• **Zero-Size Nodes**: {', '.join(zero_size)} are too small to see.")
                
        if gaps:
            report.append("\n#### 🔍 Instruction Alignment (Gap Analysis)")
            report.extend(gaps)

        # TODO: 6. LLM Visual Analysis (Future Placeholder)
        # This section is reserved for feeding the rendered PNG to a Vision LLM
        # to detect aesthetic issues or missing logical flow that XML doesn't catch.
        report.append("\n#### 👁️ Visual Semantic Analysis (Future Feature)")
        report.append("• *Note: Automated visual inspection is currently disabled. Feed the rendered image to a vision-capable LLM for final aesthetic and contextual verification.*")
            
        report.append("\n#### 📈 Graph Stats")
        report.append(f"- **Nodes**: {len(nodes)}")
        report.append(f"- **Connections**: {len(edges)}")
        
        return "\n".join(report)

    except Exception as e:
        logger.error(f"Audit failed: {e}")
        return f"Error analyzing XML: {str(e)}"

@mcp.tool()
async def archive_current_conversation(messages: List[Dict[str, str]], intention: str, metadata: Optional[Dict] = None) -> str:
    """
    Save the current chat history to the long-term archive. Not used for skills update
    
    Args:
        messages (List[Dict]): List of message objects with 'role' and 'content'.
        intention (str): LLM intention to call this tool.
        metadata (Optional[Dict]): Additional tags or context for the archive.
        
    Returns:
        str: Outcome of the archival process.
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(archive_current_conversation.__name__, intention, num_messages=len(messages))
    
    if not archiver:
        return "Error: Retriever Archiver is not initialized."
    
    try:
        doc_id = archiver.archive_conversation(messages, metadata=metadata)
        return f"✅ Conversation archived successfully with document ID: {doc_id}"
    except Exception as e:
        logger.error(f"Error archiving conversation: {e}")
        return f"❌ Failed to archive conversation: {str(e)}"

@mcp.tool()
async def archive_local_document(file_path: str, intention: str, metadata: Optional[Dict] = None) -> str:
    """
    Ingest and embed a local file (Markdown, text, etc.) into the agent's knowledge base.
    
    Args:
        file_path (str): Absolute path to the file to ingest.
        intention (str): LLM intention to call this tool.
        metadata (Optional[Dict]): Additional metadata for the document.
        
    Returns:
        str: Outcome of the ingestion process.
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(archive_local_document.__name__, intention, file_path=file_path)
    
    if not archiver:
        return "Error: Retriever Archiver is not initialized."
    
    try:
        doc_id = archiver.archive_documentation(file_path, metadata=metadata)
        return f"✅ Document '{file_path}' archived successfully with ID: {doc_id}"
    except Exception as e:
        logger.error(f"Error archiving document: {e}")
        return f"❌ Failed to archive document: {str(e)}"

@mcp.tool()
async def query_agent_archives(query: str, intention: str) -> str:
    """
    Perform a semantic RAG search across archived conversations and documentation.
    Use this to recall past solutions, technical details, or command syntax.
    
    Args:
        query (str): The question or search term.
        intention (str): LLM intention to call this tool.
        
    Returns:
        str: Augmented answer based on archived information.
    """
    logger.info(f"Intention: {intention}")
    log_tool_call_to_csv(query_agent_archives.__name__, intention, query=query)
    
    if not archiver:
        return "Error: Retriever Archiver is not initialized."
    
    try:
        result = archiver.rag_query(query)
        answer = result['answer']
        sources = ", ".join(result['sources'])
        return f"RECALLED INFORMATION:\n{answer}\n\nSOURCES: {sources}"
    except Exception as e:
        logger.error(f"Error querying archives: {e}")
        return f"❌ Failed to query archives: {str(e)}"




if __name__ == "__main__":
    mcp.run(transport="streamable-http")