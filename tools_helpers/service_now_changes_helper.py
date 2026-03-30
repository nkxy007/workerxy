import requests
import json
from datetime import datetime, timedelta
import base64
import creds as snow_creds

class ServiceNowChangeRequest:
    def __init__(self, instance_url, token):
        """
        Initialize ServiceNow API client with token authentication
        
        Args:
            instance_url: Your ServiceNow instance URL (e.g., 'https://your-instance.service-now.com')
            token: ServiceNow OAuth access token or API token
        """
        self.instance_url = instance_url.rstrip('/')
        self.token = token
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'x-sn-apikey': token
        }
    
    def create_change_request(self, short_description, description, priority='4', risk='3', impact='3', cmdb_ci=''):
        """
        Create a generic change request
        
        Args:
            short_description: Short summary of the change
            description: Detailed description
            priority: Priority 1-5 (default: 4)
            risk: Risk 1-3 (default: 3)
            impact: Impact 1-3 (default: 3)
            cmdb_ci: Name of the CI (optional)
        
        Returns:
            dict: Response from ServiceNow API
        """
        # Calculate planned start and end times (default: 2 hours from now, 1 hour duration)
        planned_start = datetime.now() + timedelta(hours=2)
        planned_end = planned_start + timedelta(hours=1)
        
        # Format dates for ServiceNow (YYYY-MM-DD HH:MM:SS)
        start_time = planned_start.strftime('%Y-%m-%d %H:%M:%S')
        end_time = planned_end.strftime('%Y-%m-%d %H:%M:%S')
        
        change_data = {
            'short_description': short_description,
            'description': description,
            'category': 'Software',
            'type': 'Standard',
            'risk': risk,
            'impact': impact,
            'priority': priority,
            'state': '1', # New
            'planned_start_date': start_time,
            'planned_end_date': end_time,
            'work_start': start_time,
            'work_end': end_time,
        }
        
        if cmdb_ci:
            change_data['cmdb_ci'] = cmdb_ci

        url = f"{self.instance_url}/api/now/table/change_request"
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                data=json.dumps(change_data),
                timeout=30
            )
            
            response.raise_for_status()
            
            return {
                'success': True,
                'status_code': response.status_code,
                'data': response.json()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': e.response.status_code if e.response else None
            }

    def create_server_reboot_change(self, server_name, additional_details=None):
        """
        Create a change request for server reboot
        
        Args:
            server_name: Name of the server (e.g., 'server.xyz.com')
            additional_details: Optional additional details for the change
        
        Returns:
            dict: Response from ServiceNow API
        """
        # Calculate planned start and end times (example: 2 hours from now, 1 hour duration)
        planned_start = datetime.now() + timedelta(hours=2)
        planned_end = planned_start + timedelta(hours=1)
        
        # Format dates for ServiceNow (YYYY-MM-DD HH:MM:SS)
        start_time = planned_start.strftime('%Y-%m-%d %H:%M:%S')
        end_time = planned_end.strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare change request data
        change_data = {
            'short_description': f'Server Reboot - {server_name}',
            'description': f'Scheduled reboot of server {server_name}',
            'justification': 'Server maintenance - system reboot required',
            'category': 'Software',  # Adjust based on your ServiceNow configuration
            'type': 'Standard',      # Standard, Normal, or Emergency
            'risk': '3',             # 1=High, 2=Medium, 3=Low
            'impact': '3',           # 1=High, 2=Medium, 3=Low
            'priority': '4',         # Adjust based on your priority matrix
            'state': '1',            # 1=New, -5=Draft (adjust based on workflow)
            'planned_start_date': start_time,
            'planned_end_date': end_time,
            'work_start': start_time,
            'work_end': end_time,
            'cmdb_ci': server_name,  # Configuration Item (server name)
            'business_service': '',  # Add business service if known
            'assignment_group': '',  # Add assignment group if known
            'assigned_to': '',       # Add assignee if known
        }
        
        # Add additional details if provided
        if additional_details:
            change_data['description'] += f'\n\nAdditional Details:\n{additional_details}'
        
        # ServiceNow Change Request API endpoint
        url = f"{self.instance_url}/api/now/table/change_request"
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                data=json.dumps(change_data),
                timeout=30
            )
            
            response.raise_for_status()  # Raises an HTTPError for bad responses
            
            return {
                'success': True,
                'status_code': response.status_code,
                'data': response.json()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': e.response.status_code if e.response else None
            }
    
    def get_change_request(self, change_number):
        """
        Retrieve a change request by change number
        
        Args:
            change_number: Change request number (e.g., 'CHG0123456')
        
        Returns:
            dict: Response from ServiceNow API
        """
        url = f"{self.instance_url}/api/now/table/change_request"
        params = {'sysparm_query': f'number={change_number}'}
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            response.raise_for_status()
            
            return {
                'success': True,
                'status_code': response.status_code,
                'data': response.json()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': e.response.status_code if e.response else None
            }

# Example usage
def main():
    # Configuration - Replace with your actual ServiceNow details
    SERVICENOW_INSTANCE = snow_creds.SERVICENOW_INSTANCE_URL
    ACCESS_TOKEN = snow_creds.SERVICENOW_ACCESS_TOKEN
    SERVER_NAME = snow_creds.SERVICENOW_SERVER_NAME
    
    # Create ServiceNow client
    sn_client = ServiceNowChangeRequest(SERVICENOW_INSTANCE, ACCESS_TOKEN)
    
    # Additional details for the change request
    additional_details = """
    Maintenance Window: Scheduled maintenance
    Expected Downtime: 15 minutes
    Rollback Plan: Server will be automatically restored if issues occur
    Testing Plan: Post-reboot system health checks will be performed
    """
    
    # Create the change request
    print(f"Creating change request for server reboot: {SERVER_NAME}")
    
    result = sn_client.create_server_reboot_change(
        server_name=SERVER_NAME,
        additional_details=additional_details
    )
    
    if result['success']:
        change_data = result['data']['result']
        change_number = change_data['number']
        sys_id = change_data['sys_id']
        
        print(f"✅ Change request created successfully!")
        print(f"Change Number: {change_number}")
        
        
    else:
        print(f"❌ Failed to create change request")
        print(f"Error: {result['error']}")
        if result.get('status_code'):
            print(f"HTTP Status Code: {result['status_code']}")

if __name__ == "__main__":
    main()
