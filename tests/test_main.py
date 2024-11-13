
import unittest
from unittest.mock import patch, MagicMock
import logging
import requests
import boto3
from src.main import (
    configure_logging,
    fetch_data,
    get_cluster_nodes,
    get_target_groups_for_node,
    register_instance_to_target_groups
)

# Sample Tests
class TestMainModule(unittest.TestCase):

    # Set up the logger to test logging outputs
    def setUp(self):
        self.logger = configure_logging()

    @patch('requests.get')
    def test_fetch_data_success(self, mock_get):
        """
        Test Case: Successful API Response Handling
        This test simulates a successful API response with status code 200 and checks if
        the function fetch_data returns the expected JSON data and makes the correct API call.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_get.return_value = mock_response

        result = fetch_data('https://testurl.com', {'Header': 'value'}, logger=self.logger)
        self.assertEqual(result, {'data': 'test'})  # Ensure correct data is returned
        mock_get.assert_called_once_with('https://testurl.com', headers={'Header': 'value'}, params=None)  # Ensure the API call was made correctly

    @patch('requests.get')
    def test_fetch_data_failure(self, mock_get):
        """
        Test Case: Failure Handling in fetch_data
        This test simulates a failure in the API request by raising a RequestException,
        and ensures that fetch_data returns None and logs the failure.
        """
        mock_get.side_effect = requests.exceptions.RequestException("API request failed")

        result = fetch_data('https://testurl.com', {'Header': 'value'}, logger=self.logger)
        self.assertIsNone(result)  # Ensure None is returned on failure
        mock_get.assert_called_once()  # Ensure that the API call was made

    @patch('requests.get')
    def test_get_cluster_nodes(self, mock_get):
        """
        Test Case: Retrieve Cluster Nodes
        This test checks if get_cluster_nodes can correctly retrieve a list of nodes from the API.
        It simulates a response with two node items and verifies the output of the function.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': [{'id': 'node1'}, {'id': 'node2'}]}
        mock_get.return_value = mock_response

        api_key = 'test_api_key'
        cluster_id = 'test_cluster_id'
        result = get_cluster_nodes(api_key, cluster_id, self.logger)
        self.assertEqual(len(result), 2)  # Ensure two nodes are returned
        mock_get.assert_called_once()  # Ensure the API call was made correctly

    @patch('requests.get')
    def test_get_target_groups_for_node(self, mock_get):
        """
        Test Case: Retrieve Target Groups for a Node
        This test checks if get_target_groups_for_node can correctly retrieve target groups 
        associated with a specific node by simulating a response with two target groups.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'eks': {
                'targetGroups': [
                    {'arn': 'tg_arn_1', 'port': 80},
                    {'arn': 'tg_arn_2', 'port': 443}
                ]
            }
        }
        mock_get.return_value = mock_response

        api_key = 'test_api_key'
        cluster_id = 'test_cluster_id'
        node_config_id = 'test_node_config_id'
        result = get_target_groups_for_node(api_key, cluster_id, node_config_id, self.logger)
        self.assertEqual(len(result), 2)  # Ensure two target groups are returned
        mock_get.assert_called_once()  # Ensure the API call was made correctly

    @patch('boto3.client')
    def test_register_instance_to_target_groups(self, mock_boto_client):
        """
        Test Case: Register Instance to Target Groups
        This test simulates the scenario where an instance is registered to a new target group 
        and already registered to another. It checks if the function interacts correctly with AWS 
        services (e.g., boto3 client for registering/deregistering instances).
        """
        mock_elb_client = MagicMock()
        mock_boto_client.return_value = mock_elb_client
        
        # Mock paginator to simulate AWS responses for target groups
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{'TargetGroups': [{'TargetGroupArn': 'tg_arn_1'}]}]
        mock_elb_client.get_paginator.return_value = mock_paginator

        # Mock describe_target_health to indicate the instance is registered in 'tg_arn_1'
        mock_elb_client.describe_target_health.return_value = {
            'TargetHealthDescriptions': [
                {'Target': {'Id': 'test_instance_id'}}
            ]
        }

        # Mock register_targets and deregister_targets methods
        mock_elb_client.register_targets.return_value = {}
        mock_elb_client.deregister_targets.return_value = {}

        aws_region = 'us-west-1'
        instance_id = 'test_instance_id'
        target_groups = [{'arn': 'tg_arn_2', 'port': 80}]  # Target group to register to

        result = register_instance_to_target_groups(aws_region, instance_id, target_groups, self.logger)
        self.assertIn('registered', result)
        self.assertIn('already_registered', result)
        self.assertIn('deregistered', result)
        self.assertIn('failed', result)
        mock_boto_client.assert_called_once_with('elbv2', region_name=aws_region)

    @patch('boto3.client')
    def test_register_instance_no_target_groups(self, mock_boto_client):
        """
        Test Case: No Target Groups Provided
        This test checks the behavior when no target groups are provided in the input. 
        The function should not attempt any AWS operations and return empty results.
        """
        mock_elb_client = MagicMock()
        mock_boto_client.return_value = mock_elb_client

        aws_region = 'us-west-1'
        instance_id = 'test_instance_id'
        target_groups = []  # No target groups provided

        result = register_instance_to_target_groups(aws_region, instance_id, target_groups, self.logger)
        self.assertEqual(result, {'registered': [], 'already_registered': [], 'deregistered': [], 'failed': []})

    @patch('boto3.client')
    def test_partial_registration_success(self, mock_boto_client):
        """
        Test Case: Partial Registration Success
        This test simulates a situation where the instance is successfully registered to one target 
        group and fails to register to another. It checks if the function handles partial success 
        correctly and logs the failed registration attempt.
        """
        mock_elb_client = MagicMock()
        mock_boto_client.return_value = mock_elb_client

        # Simulate AWS response where instance is not registered in both target groups
        mock_elb_client.describe_target_health.side_effect = [
            {'TargetHealthDescriptions': []},  # First target group: instance not registered
            {'TargetHealthDescriptions': []}   # Second target group: instance not registered
        ]
        # Simulate register_targets where the first call succeeds and second fails
        mock_elb_client.register_targets.side_effect = [None, Exception("Failed to register")]

        aws_region = 'us-west-1'
        instance_id = 'test_instance_id'
        target_groups = [{'arn': 'tg_arn_1', 'port': 80}, {'arn': 'tg_arn_2', 'port': 443}]

        result = register_instance_to_target_groups(aws_region, instance_id, target_groups, self.logger)

        # Ensure tg_arn_1 was successfully registered
        self.assertIn('tg_arn_1', result['registered'])

        # Ensure tg_arn_2 failed to register
        failed_arns = [item['arn'] for item in result['failed']]
        self.assertIn('tg_arn_2', failed_arns)

        # Verify other parts of the result
        self.assertEqual(result['already_registered'], [])
        self.assertEqual(result['deregistered'], [])

        # Assert boto3 client was called with the correct parameters
        mock_boto_client.assert_called_once_with('elbv2', region_name=aws_region)

    @patch('boto3.client')
    def test_register_instance_target_groups_success(self, mock_boto_client):
        """
        Test Case: Successful Registration to a New Target Group
        This test checks if the instance is correctly registered to a target group when it's not
        already registered and no errors occur.
        """
        mock_elb_client = MagicMock()
        mock_boto_client.return_value = mock_elb_client

        # Mock describe_target_health to indicate the instance is not registered in any target groups
        mock_elb_client.describe_target_health.side_effect = [
            {'TargetHealthDescriptions': []}  # Instance not registered in any target group
        ]

        # Mock register_targets method to simulate successful registration
        mock_elb_client.register_targets.return_value = {}

        aws_region = 'us-west-1'
        instance_id = 'test_instance_id'
        target_groups = [{'arn': 'tg_arn_1', 'port': 80}]  # New target group to register to

        result = register_instance_to_target_groups(aws_region, instance_id, target_groups, self.logger)

        # Ensure tg_arn_1 was successfully registered
        self.assertIn('tg_arn_1', result['registered'])
        self.assertEqual(result['already_registered'], [])
        self.assertEqual(result['deregistered'], [])
        self.assertEqual(result['failed'], [])

        mock_boto_client.assert_called_once_with('elbv2', region_name=aws_region)

    @patch('boto3.client')
    def test_register_instance_no_target_groups_empty(self, mock_boto_client):
        """
        Test Case: No Target Groups Provided (Empty List)
        This test checks the behavior when no target groups are provided in the input.
        """
        mock_elb_client = MagicMock()
        mock_boto_client.return_value = mock_elb_client

        aws_region = 'us-west-1'
        instance_id = 'test_instance_id'
        target_groups = []  # No target groups provided

        result = register_instance_to_target_groups(aws_region, instance_id, target_groups, self.logger)

        # Ensure that no operations were performed
        self.assertEqual(result, {'registered': [], 'already_registered': [], 'deregistered': [], 'failed': []})
        mock_boto_client.assert_called_once_with('elbv2', region_name=aws_region)

    @patch('boto3.client')
    def test_register_instance_with_target_groups_partial_success(self, mock_boto_client):
        """
        Test Case: Partial Success in Registration
        This test simulates a situation where one target group registration succeeds and another fails.
        """
        mock_elb_client = MagicMock()
        mock_boto_client.return_value = mock_elb_client

        # Simulate instance not registered to any target groups
        mock_elb_client.describe_target_health.side_effect = [
            {'TargetHealthDescriptions': []},  # Instance not registered to any target group
            {'TargetHealthDescriptions': []}
        ]

        # Simulate successful registration to tg_arn_1, failure to register tg_arn_2
        mock_elb_client.register_targets.side_effect = [
            None,  # Successful registration to tg_arn_1
            Exception("Failed to register tg_arn_2")  # Failure for tg_arn_2
        ]

        aws_region = 'us-west-1'
        instance_id = 'test_instance_id'
        target_groups = [{'arn': 'tg_arn_1', 'port': 80}, {'arn': 'tg_arn_2', 'port': 443}]

        result = register_instance_to_target_groups(aws_region, instance_id, target_groups, self.logger)

        # Ensure tg_arn_1 was successfully registered
        self.assertIn('tg_arn_1', result['registered'])
        # Ensure tg_arn_2 failed to register
        self.assertIn('tg_arn_2', [item['arn'] for item in result['failed']])

        mock_boto_client.assert_called_once_with('elbv2', region_name=aws_region)


    @patch('boto3.client')
    def test_register_instance_invalid_target_group(self, mock_boto_client):
        """
        Test Case: Invalid Target Group ARN
        This test checks the case where the target group ARN is invalid or does not exist.
        """
        mock_elb_client = MagicMock()
        mock_boto_client.return_value = mock_elb_client

        # Simulate instance not registered to any target groups
        mock_elb_client.describe_target_health.side_effect = [
            {'TargetHealthDescriptions': []}
        ]

        # Simulate a failure to register due to invalid target group ARN
        mock_elb_client.register_targets.side_effect = Exception("Invalid target group ARN")

        aws_region = 'us-west-1'
        instance_id = 'test_instance_id'
        target_groups = [{'arn': 'invalid_tg_arn', 'port': 80}]  # Invalid ARN

        result = register_instance_to_target_groups(aws_region, instance_id, target_groups, self.logger)

        # Ensure the invalid target group is reported as a failure
        self.assertIn('invalid_tg_arn', [item['arn'] for item in result['failed']])
        self.assertEqual(result['registered'], [])
        self.assertEqual(result['already_registered'], [])
        self.assertEqual(result['deregistered'], [])

    @patch('boto3.client')
    def test_deregister_instance_no_target_groups(self, mock_boto_client):
        """
        Test Case: Deregister Instance When No Target Groups Provided
        This test checks the behavior when the target_groups list is empty, and the instance should be
        deregistered from all existing target groups.
        """
        mock_elb_client = MagicMock()
        mock_boto_client.return_value = mock_elb_client

        # Simulate instance already registered in one target group
        mock_elb_client.describe_target_health.return_value = {
            'TargetHealthDescriptions': [{'Target': {'Id': 'test_instance_id'}}]
        }

        # Simulate successful deregistration
        mock_elb_client.deregister_targets.return_value = {}

        aws_region = 'us-west-1'
        instance_id = 'test_instance_id'
        target_groups = []  # No target groups provided, expect deregistration

        result = register_instance_to_target_groups(aws_region, instance_id, target_groups, self.logger)

        # Ensure instance was deregistered from the target group
        self.assertIn('deregistered', result)
        self.assertEqual(result['registered'], [])
        self.assertEqual(result['already_registered'], [])
        self.assertEqual(result['failed'], [])

        mock_boto_client.assert_called_once_with('elbv2', region_name=aws_region)


if __name__ == '__main__':
    unittest.main()