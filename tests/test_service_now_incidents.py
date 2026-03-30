import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os
import requests

# Add the parent directory to sys.path to import the helper
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools_helpers.service_now_incidents_helper import ServiceNowIncident

class TestServiceNowIncident(unittest.TestCase):
    def setUp(self):
        self.instance_url = "https://dev12345.service-now.com"
        self.token = "fake-token"
        self.client = ServiceNowIncident(self.instance_url, self.token)

    @patch('tools_helpers.service_now_incidents_helper.requests.post')
    @patch('tools_helpers.service_now_incidents_helper.ServiceNowIncident.resolve_user_name')
    @patch('tools_helpers.service_now_incidents_helper.ServiceNowIncident.resolve_group_name')
    def test_create_incident_success(self, mock_resolve_group, mock_resolve_user, mock_post):
        # Mocking resolutions
        mock_resolve_user.return_value = "user_sys_id"
        mock_resolve_group.return_value = "group_sys_id"
        
        # Mocking POST response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"result": {"number": "INC0010001", "sys_id": "incident_sys_id"}}
        mock_post.return_value = mock_response

        # Call the method
        result = self.client.create_incident(
            short_description="Test Incident",
            description="Detail description",
            caller_id="Fred Luddy",
            urgency=1,
            impact=1,
            assignment_group="Software"
        )

        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['status_code'], 201)
        self.assertEqual(result['data']['result']['number'], "INC0010001")
        
        # Verify resolution calls
        mock_resolve_user.assert_called_with("Fred Luddy")
        mock_resolve_group.assert_called_with("Software")
        
        # Verify POST payload
        args, kwargs = mock_post.call_args
        payload = json.loads(kwargs['data'])
        self.assertEqual(payload['short_description'], "Test Incident")
        self.assertEqual(payload['caller_id'], "user_sys_id")
        self.assertEqual(payload['assignment_group'], "group_sys_id")
        self.assertEqual(payload['urgency'], "1")

    @patch('tools_helpers.service_now_incidents_helper.requests.post')
    def test_create_incident_with_sys_ids(self, mock_post):
        # Mocking POST response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"result": {"number": "INC0010001"}}
        mock_post.return_value = mock_response

        # Call the method with 32-char hex IDs
        user_sys_id = "a" * 32
        group_sys_id = "b" * 32
        
        result = self.client.create_incident(
            short_description="Test with sys_ids",
            caller_id=user_sys_id,
            assignment_group=group_sys_id
        )

        # Assertions
        self.assertTrue(result['success'])
        args, kwargs = mock_post.call_args
        payload = json.loads(kwargs['data'])
        self.assertEqual(payload['caller_id'], user_sys_id)
        self.assertEqual(payload['assignment_group'], group_sys_id)

    def test_create_incident_resolution_failure(self):
        with patch('tools_helpers.service_now_incidents_helper.ServiceNowIncident.resolve_user_name', return_value=None):
            result = self.client.create_incident(
                short_description="Fail Resolution",
                caller_id="NonExistentUser"
            )
            self.assertFalse(result['success'])
            self.assertIn("Could not resolve caller name", result['error'])

    @patch('tools_helpers.service_now_incidents_helper.requests.post')
    def test_create_incident_api_error(self, mock_post):
        # Mocking API error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Internal Server Error", response=mock_response)
        mock_post.return_value = mock_response

        result = self.client.create_incident(short_description="Fail API")
        self.assertFalse(result['success'])
        self.assertEqual(result['status_code'], 500)

if __name__ == '__main__':
    unittest.main()
