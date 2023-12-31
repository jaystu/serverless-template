import sys
from uuid import uuid4
import os
import json
from unittest import TestCase
from unittest.mock import MagicMock, patch
from boto3 import resource, client
import moto
from aws_lambda_powertools.utilities.validation import validate

# Import the Globals, Classes, Schemas, and Functions from the Lambda Handler
sys.path.append('.') # required for CodePipeline
from lambda_function.app import LambdaDynamoDBClass
from lambda_function.app import lambda_handler, lambda_handler_helper

_DDB_PK = 'id'

# Mock all AWS Services in use
@moto.mock_dynamodb

class TestPetLambdaFunction(TestCase):
    """
    Test class for the application sample AWS Lambda Function
    """

    # Test Setup
    def setUp(self) -> None:
        """
        Create mocked resources for use during tests
        """

        # Mock environment & override resources
        self.test_ddb_table_name = "unit_test_ddb"

        # Set up the services: construct a (mocked!) DynamoDB table
        dynamodb = resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName = self.test_ddb_table_name,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": _DDB_PK, "AttributeType": "S"}],
            BillingMode='PAY_PER_REQUEST'
            )

        # Establish the "GLOBAL" environment for use in tests.
        mocked_dynamodb_resource = resource("dynamodb")
        mocked_dynamodb_resource = { "resource" : resource('dynamodb'),
                                     "table_name" : self.test_ddb_table_name  }
        self.mocked_dynamodb_class = LambdaDynamoDBClass(mocked_dynamodb_resource)
        
    def tearDown(self) -> None:
        # Remove (mocked!) DynamoDB Table
        dynamodb_resource = client("dynamodb", region_name="us-east-1")
        dynamodb_resource.delete_table(TableName = self.test_ddb_table_name )


    def load_test_event(self, test_event_file_name: str) ->  dict:
        """
        Loads and validate test events from the file system
        """
        event_file_name = f"tests/events/{test_event_file_name}.json"
        with open(event_file_name, "r", encoding='UTF-8') as file_handle:
            event = json.load(file_handle)
            return event
            
    # Patch the Global Class and any function calls
    @patch("lambda_function.app.LambdaDynamoDBClass")
    @patch("lambda_function.app.lambda_handler_helper")
    def test_lambda_handler(self,
                            patch_lambda_handler_helper : MagicMock,
                            patch_lambda_dynamodb_class : MagicMock
                            ):

        # Test setup - Return a mock for the global variables and resources
        patch_lambda_dynamodb_class.return_value = self.mocked_dynamodb_class

        return_value_200 = {"statusCode" : 200, "body":"OK"}
        patch_lambda_handler_helper.return_value = return_value_200

        # Run Test using a test event from /tests/events/*.json
        test_event = self.load_test_event("get_event_sample")
        response_value = lambda_handler(event=test_event, context=None)

        # Validate the function was called with the mocked globals
        # and event values
        patch_lambda_handler_helper.assert_called_once_with(test_event, self.mocked_dynamodb_class)

        self.assertEqual(return_value_200, response_value)

    
    def test_get_happy(self):
        pk_value = str(uuid4())
        data = str(uuid4())
        
        # Populate data for the tests
        self.mocked_dynamodb_class.table.put_item(Item={_DDB_PK: pk_value, 
                                                "data": data})

        # Set the id in the event to be the one we just created
        test_event = self.load_test_event("get_event_sample")
        test_event['pathParameters'][_DDB_PK] = pk_value
        
        response = lambda_handler_helper(event=test_event, dynamo_db=self.mocked_dynamodb_class)
        self.assertEqual(response["statusCode"] , 200)
        self.assertIn(pk_value, response["body"])
        self.assertIn(data, response["body"])
        
    def test_get_notFound(self):
        test_event = self.load_test_event("get_event_sample")
        
        response = lambda_handler_helper(event=test_event, dynamo_db=self.mocked_dynamodb_class)
        self.assertEqual(response["statusCode"] , 404)
        
    def test_create_happy(self):
        pk_value = str(uuid4())
        
        # Specify the pk_value of the record we want to create so we can lookup later
        test_event = self.load_test_event("create_event_sample")
        test_event['body'] = "{\"" +_DDB_PK+"\":\""+pk_value+"\"}"
        
        response = lambda_handler_helper(event=test_event, dynamo_db=self.mocked_dynamodb_class)
        
        self.assertEqual(response["statusCode"] , 200)
        
        # Verify item actually got created in the table
        item = self.mocked_dynamodb_class.table.get_item(Key={_DDB_PK: pk_value}).get('Item')
        self.assertIsNotNone(item)
        self.assertIsNotNone(item['created'])
        self.assertIsNotNone(item['modified'])
        
        
    def test_create_existing(self):
        # Create a preexisting record
        pk_value = str(uuid4())
        data = str(uuid4())
        self.mocked_dynamodb_class.table.put_item(Item={_DDB_PK: pk_value, 
                                                "data": data})
        
        # Set the id in the event to be the one we just created
        test_event = self.load_test_event("create_event_sample")
        test_event['body'] = "{\""+_DDB_PK+"\":\""+pk_value+"\"}"
        
        response = lambda_handler_helper(event=test_event, dynamo_db=self.mocked_dynamodb_class)
        self.assertEqual(response["statusCode"] , 400)
        self.assertEqual('Item already exists.', response['body'])
        
    def test_delete_happy(self):
        pk_value = str(uuid4())
        data = str(uuid4())
        
        # Create record so we can test deleting it
        self.mocked_dynamodb_class.table.put_item(Item={_DDB_PK: pk_value, 
                                                "data": data})
        
        # Specify the id of the record we want to create so we can lookup later
        test_event = self.load_test_event("delete_event_sample")
        test_event['pathParameters'][_DDB_PK] = pk_value
        
        response = lambda_handler_helper(event=test_event, dynamo_db=self.mocked_dynamodb_class)
        
        self.assertEqual(response["statusCode"] , 200)
        
        # Verify item actually got deleted in the table
        self.assertIsNone(self.mocked_dynamodb_class.table.get_item(Key={_DDB_PK: pk_value}).get('Item'))

    def test_delete_nonExistent(self):
        # Id in event is non existent
        test_event = self.load_test_event("delete_event_sample")
        
        response = lambda_handler_helper(event=test_event, dynamo_db=self.mocked_dynamodb_class)
        
        self.assertEqual(response["statusCode"] , 200)
        
    def test_update_happy(self):
        pk_value = str(uuid4())
        data = str(uuid4())
        
        # Create record so we can test updating it
        self.mocked_dynamodb_class.table.put_item(Item={_DDB_PK: pk_value, 
                                                "data": data})
                                                
        # Set the id in the event to be the one we just created
        test_event = self.load_test_event("update_event_sample")
        test_event['body'] = "{\""+_DDB_PK+"\":\""+pk_value+"\"}"
        test_event['pathParameters'][_DDB_PK] = pk_value
        
        response = lambda_handler_helper(event=test_event, dynamo_db=self.mocked_dynamodb_class)
        
        self.assertEqual(response["statusCode"] , 200)
        
        # Verify item actually got updated
        new_item = self.mocked_dynamodb_class.table.get_item(Key={_DDB_PK: pk_value}).get('Item')
        self.assertIsNotNone(new_item)
        self.assertIsNotNone(new_item['modified'])
        
        
    def test_update_id_mismatch(self):
        pk_value = str(uuid4())
                                                
        # Set the id in the event to be the one we just created
        test_event = self.load_test_event("update_event_sample")
        test_event['body'] = "{\""+_DDB_PK+"\":\""+pk_value+"\"}"
        test_event['pathParameters'][_DDB_PK] = pk_value + "different"
        
        response = lambda_handler_helper(event=test_event, dynamo_db=self.mocked_dynamodb_class)
        
        self.assertEqual(response["statusCode"] , 400)
        self.assertEqual('Id in path does not match id in body', response['body'])
        
    def test_update_notExist(self):
        pk_value = str(uuid4())
                                                
        # Set the id in the event to be the one we just created
        test_event = self.load_test_event("update_event_sample")
        test_event['body'] = "{\""+_DDB_PK+"\":\""+pk_value+"\"}"
        test_event['pathParameters'][_DDB_PK] = pk_value
        
        response = lambda_handler_helper(event=test_event, dynamo_db=self.mocked_dynamodb_class)
        
        self.assertEqual(response["statusCode"] , 404)