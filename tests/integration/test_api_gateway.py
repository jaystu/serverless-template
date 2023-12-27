import os

import boto3
import pytest
import requests
from uuid import uuid4

"""
Make sure env variable AWS_SAM_STACK_NAME exists with the name of the stack we are going to test. 
"""


class TestApiGateway:

    @pytest.fixture()
    def api_gateway_url(self):
        """ Get the API Gateway URL from Cloudformation Stack outputs """
        stack_name = os.environ.get("AWS_SAM_STACK_NAME")

        if stack_name is None:
            raise ValueError('Please set the AWS_SAM_STACK_NAME environment variable to the name of your stack')

        client = boto3.client("cloudformation")

        try:
            response = client.describe_stacks(StackName=stack_name)
        except Exception as e:
            raise Exception(
                f"Cannot find stack {stack_name} \n" f'Please make sure a stack with the name "{stack_name}" exists'
            ) from e

        stacks = response["Stacks"]
        print(stacks)
        stack_outputs = stacks[0]["Outputs"]
        api_outputs = [output for output in stack_outputs if output["OutputKey"] == "PetApi"]

        if not api_outputs:
            raise KeyError(f"PetApi not found in stack {stack_name}")

        return api_outputs[0]["OutputValue"]  # Extract url from stack outputs
        
    def test_api_gateway_full_happy_path(self, api_gateway_url):
        # Setup
        id = str(uuid4())
        url_with_path_param = api_gateway_url + id
        
        # Create record
        response = requests.post(api_gateway_url, json={'id': id})
        
        # Get old record
        response = requests.get(url_with_path_param)
        old_modified_timestamp = response.json()['modified']
        
        # Update record
        response = requests.put(url_with_path_param, json={'id': id})
        
        # Get new record
        response = requests.get(url_with_path_param)
        new_modified_timestamp = response.json()['modified']
        
        # Delete record
        response = requests.delete(url_with_path_param)
        
        # Get non existent record
        response = requests.get(url_with_path_param)
        non_existent_response = response.status_code
        
        # Validate
        assert old_modified_timestamp < new_modified_timestamp
        assert non_existent_response == 404
        

    def test_api_gateway_get(self, api_gateway_url):
        url = api_gateway_url + "1" # add the id path param
        response = requests.get(url)

        assert response.status_code == 404
        
    def test_api_gateway_post(self, api_gateway_url):
        id = str(uuid4())
        response = requests.post(api_gateway_url, json={'id': id})

        assert response.status_code == 200
        
        url = api_gateway_url + id # add the id path param
        response = requests.get(url)
        created = response.json()['created']
        modified = response.json()['modified']
        
        assert created == modified
        
        # cleanup
        requests.delete(api_gateway_url + id)
        
    def test_api_gateway_put(self, api_gateway_url):
        url = api_gateway_url + "1" # add the id path param
        response = requests.put(url, json={'id': '1'})

        assert response.status_code == 404
        
    def test_api_gateway_delete(self, api_gateway_url):
        url = api_gateway_url + "1" # add the id path param
        response = requests.delete(url)

        assert response.status_code == 200
