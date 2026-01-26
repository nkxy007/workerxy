import requests
import json
from datetime import datetime, timedelta
import snow_creds


class ServiceNowIncident:
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
    
    def get_incidents(self, limit=100, query_params=None, display_value=True):
        """
        Retrieve incidents from ServiceNow
        
        Args:
            limit: Maximum number of incidents to retrieve (default: 100)
            query_params: Optional dict of query parameters for filtering
                         Example: {'state': '1', 'priority': '1'}
            display_value: If True, return display values. If False, return raw values (sys_ids).
        
        Returns:
            dict: Response from ServiceNow API with list of incidents
        """
        url = f"{self.instance_url}/api/now/table/incident"
        
        params = {
            'sysparm_limit': limit,
            'sysparm_display_value': 'true' if display_value else 'false'
        }
        
        # Build query string if filters provided
        if query_params:
            query_parts = [f"{key}={value}" for key, value in query_params.items()]
            params['sysparm_query'] = '^'.join(query_parts)
        
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
                'data': response.json(),
                'count': len(response.json().get('result', []))
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': e.response.status_code if e.response else None
            }
    
    def get_incident_by_id(self, incident_id):
        """
        Retrieve a specific incident by incident number or sys_id
        
        Args:
            incident_id: Incident number (e.g., 'INC0123456') or sys_id
        
        Returns:
            dict: Response from ServiceNow API with incident details
        """
        url = f"{self.instance_url}/api/now/table/incident"
        
        # Check if it's a sys_id (32-character hex) or incident number
        if len(incident_id) == 32 and all(c in '0123456789abcdef' for c in incident_id.lower()):
            # It's a sys_id, query directly
            url = f"{url}/{incident_id}"
            params = {'sysparm_display_value': 'true'}
            
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
        else:
            # It's an incident number, query by number
            params = {
                'sysparm_query': f'number={incident_id}',
                'sysparm_display_value': 'true'
            }
            
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=30
                )
                
                response.raise_for_status()
                
                result_data = response.json()
                
                # Check if incident was found
                if result_data.get('result') and len(result_data['result']) > 0:
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'data': {'result': result_data['result'][0]}
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Incident {incident_id} not found',
                        'status_code': 404
                    }
                
            except requests.exceptions.RequestException as e:
                return {
                    'success': False,
                    'error': str(e),
                    'status_code': e.response.status_code if e.response else None
                }
    
    def get_active_incidents(self, priority=None):
        """
        Retrieve active incidents (state < 6)
        
        Args:
            priority: Optional priority filter (1=Critical, 2=High, 3=Moderate, 4=Low, 5=Planning)
        
        Returns:
            dict: Response from ServiceNow API with active incidents
        """
        query_params = {'active': 'true'}
        
        if priority:
            query_params['priority'] = str(priority)
        
        return self.get_incidents(query_params=query_params)
    
    def get_my_incidents(self, user_sys_id):
        """
        Retrieve incidents assigned to a specific user
        
        Args:
            user_sys_id: The sys_id of the user
        
        Returns:
            dict: Response from ServiceNow API with user's incidents
        """
        query_params = {'assigned_to': user_sys_id}
        return self.get_incidents(query_params=query_params)
    
    def resolve_group_name(self, group_name):
        """
        Resolve a group name to its sys_id
        
        Args:
            group_name: Name of the group (e.g., 'Software')
            
        Returns:
            str: sys_id of the group or None if not found
        """
        url = f"{self.instance_url}/api/now/table/sys_user_group"
        params = {
            'sysparm_query': f'name={group_name}^active=true',
            'sysparm_limit': 1,
            'sysparm_fields': 'sys_id'
        }
        #params = {
        #'sysparm_limit': 100,
        #'sysparm_fields': 'sys_id,name,u_name,type,active'  # Get all relevant fields
        #}
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            result = response.json().get('result', [])
            
            if result and len(result) > 0:
                return result[0]['sys_id']
            return None
            
        except Exception as e:
            print(f"Error resolving group name: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_group_incidents(self, group_id):
        """
        Retrieve incidents assigned to a specific group
        
        Args:
            group_id: The sys_id or name of the assignment group
            
        Returns:
            dict: Response from ServiceNow API with group's incidents
        """
        # Check if group_id looks like a sys_id (32 hex chars)
        is_sys_id = len(group_id) == 32 and all(c in '0123456789abcdef' for c in group_id.lower())
        
        real_group_id = group_id
        if not is_sys_id:
            # Try to resolve name to ID
            resolved_id = self.resolve_group_name(group_id)
            if resolved_id:
                real_group_id = resolved_id
            else:
                # If resolution fails, return error immediately or let the API fail with the name
                # API usually requires sys_id for reference fields in queries
                return {
                    'success': False,
                    'error': f"Could not resolve group name '{group_id}' to a sys_id",
                    'status_code': 400
                }

        query_params = {'assignment_group': real_group_id}
        return self.get_incidents(query_params=query_params)
        
    def get_unassigned_group_incidents(self, group_id):
        """
        Retrieve unassigned incidents for a specific group (by name )
        
        Args:
            group_id: The sys_id or name of the assignment group
            
        Returns:
            dict: Response from ServiceNow API with group's unassigned incidents
        """
        # Check if group_id looks like a sys_id
        is_sys_id = len(group_id) == 32 and all(c in '0123456789abcdef' for c in group_id.lower())
        
        real_group_id = group_id
        if not is_sys_id:
            resolved_id = self.resolve_group_name(group_id)
            if resolved_id:
                real_group_id = resolved_id
            else:
                return {
                    'success': False,
                    'error': f"Could not resolve group name '{group_id}' to a sys_id",
                    'status_code': 400
                }

        # Query for incidents in this group where assigned_to is empty
        # We append the encoded query operator `^assigned_toISEMPTY` to the value
        # This works because the query builder joins with ^, so we just extend the first param.
        query_params = {'assignment_group': f'{real_group_id}^assigned_toISEMPTY'}
        return self.get_incidents(query_params=query_params)


# Example usage
def main():
    # Configuration - Replace with your actual ServiceNow details
    SERVICENOW_INSTANCE = snow_creds.SERVICENOW_INSTANCE
    ACCESS_TOKEN = snow_creds.ACCESS_TOKEN
    
    # Create ServiceNow client
    sn_client = ServiceNowIncident(SERVICENOW_INSTANCE, ACCESS_TOKEN)
    
    print("=" * 70)
    print("ServiceNow Incident Retrieval Examples")
    print("=" * 70)
    
    # Example 1: Get all incidents (limited to 10 for demo)
    print("\n1. Retrieving recent incidents...")
    result = sn_client.get_incidents(limit=10)
    
    if result['success']:
        incidents = result['data']['result']
        print(f"✅ Retrieved {result['count']} incidents")
        
        for inc in incidents[:3]:  # Show first 3
            print(f"\n  - Number: {inc.get('number')}")
            print(f"    Short Description: {inc.get('short_description')}")
            print(f"    State: {inc.get('state')}")
            print(f"    Priority: {inc.get('priority')}")
            print(f"    Opened by: {inc.get('opened_by')}")
    else:
        print(f"❌ Failed to retrieve incidents: {result['error']}")
    
    # Example 2: Get specific incident by ID
    print("\n" + "=" * 70)
    print("2. Retrieving specific incident by ID...")
    
    INCIDENT_ID = input("which incident details you want to show? ") # Replace with actual incident number
    
    result = sn_client.get_incident_by_id(INCIDENT_ID)
    
    if result['success']:
        incident = result['data']['result']
        print(f"✅ Incident found: {incident.get('number')}")
        print(f"\n  Short Description: {incident.get('short_description')}")
        print(f"  Description: {incident.get('description')}")
        print(f"  State: {incident.get('state')}")
        print(f"  Priority: {incident.get('priority')}")
        print(f"  Assigned To: {incident.get('assigned_to')}")
        print(f"  Created: {incident.get('sys_created_on')}")
        print(f"  Updated: {incident.get('sys_updated_on')}")
        print(f"  Caller: {incident.get('caller_id')}")
    else:
        print(f"❌ Failed to retrieve incident: {result['error']}")
    
    # Example 3: Get active high-priority incidents
    print("\n" + "=" * 70)
    print("3. Retrieving active 2+ priority incidents...")
    
    result_low_priority = sn_client.get_active_incidents(priority=4)
    result_high_priority = sn_client.get_active_incidents(priority=2)
    result_medium_priority = sn_client.get_active_incidents(priority=3)
    # Combine results from high, medium priority
    result = {'success': True, 'data': {'result': []}, 'count': 0}
    if result_high_priority['success'] and result_medium_priority['success']:
        combined_incidents = result_high_priority['data']['result'] + result_medium_priority['data']['result']
        result['data']['result'] = combined_incidents
        result['count'] = len(combined_incidents)
    elif result_high_priority['success']:
        result = result_high_priority
    elif result_medium_priority['success']:
        result = result_medium_priority
    else:
        result = {'success': False, 'error': 'Failed to retrieve high and medium priority incidents'}
    
    if result['success']:
        print(f"✅ Found {result['count']} active incidents")
        
        for inc in result['data']['result'][:11]:  # Show first 11
            print(f"\n  - {inc.get('number')}: {inc.get('short_description')}")
            print(f"    Assigned to: {inc.get('assigned_to', 'Unassigned')}")
    else:
        print(f"❌ Failed to retrieve incidents: {result['error']}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()