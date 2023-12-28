import json
import datetime
from os import environ
from typing import Any, Dict
from boto3 import resource
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

# Globally scoped resources
# Initialize the resources once per Lambda execution environment by using global scope.
_LAMBDA_DYNAMODB_RESOURCE = { "resource" : resource('dynamodb'), 
                              "table_name" : environ.get("DYNAMODB_TABLE_NAME","NONE") }

# Define a Global class an AWS Resource: Amazon DynamoDB. 
class LambdaDynamoDBClass:
    """
    AWS DynamoDB Resource Class
    """
    def __init__(self, lambda_dynamodb_resource):
        """
        Initialize a DynamoDB Resource
        """
        self.resource = lambda_dynamodb_resource["resource"]
        self.table_name = lambda_dynamodb_resource["table_name"]
        self.table = self.resource.Table(self.table_name)

def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda Entry Point
    """
    # Use the Global variables to optimize AWS resource connections
    global _LAMBDA_DYNAMODB_RESOURCE

    dynamo_db = LambdaDynamoDBClass(_LAMBDA_DYNAMODB_RESOURCE)
    
    return lambda_handler_helper(event, dynamo_db)
    
def lambda_handler_helper(event: APIGatewayProxyEvent, dynamo_db: LambdaDynamoDBClass) -> Dict[str, Any]:
    
    http_method = event['httpMethod']
    path_parameters = event['pathParameters']

    if http_method == 'GET':
        if path_parameters and 'id' in path_parameters:
            return get_item(dynamo_db, path_parameters['id'])
        else:
            return {
                'statusCode': 400,
                'body': 'Invalid GET request'
            }
    elif http_method == 'POST':
        item_data = json.loads(event['body'])
        return create_item(dynamo_db, item_data)
    elif http_method == 'PUT':
        if path_parameters and 'id' in path_parameters:
            item_id = path_parameters['id']
            item_data = json.loads(event['body'])
            # if item_id != item_data['id']:
            #     return {
            #         'statusCode': 400,
            #         'body': 'Id in path does not match id in body'
            #     }
            return update_item(dynamo_db, item_id, item_data)
        else:
            return {
                'statusCode': 400,
                'body': 'Invalid PUT request'
            }
    elif http_method == 'DELETE':
        if path_parameters and 'id' in path_parameters:
            item_id = path_parameters['id']
            return delete_item(dynamo_db, item_id)
        else:
            return {
                'statusCode': 400,
                'body': 'Invalid DELETE request'
            }
    else:
        return {
            'statusCode': 400,
            'body': 'Invalid HTTP method'
        }
        
def create_item(dynamo_db: LambdaDynamoDBClass, item_data):
    try:
        # Get the current timestamp as the item's "created" and "modified" field
        now = datetime.datetime.utcnow().isoformat()
        item_data['created'] = now
        item_data['modified'] = now
        
        # Define a condition expression to check if the item does not already exist
        condition_expression = "attribute_not_exists(id)"

        # Put the item in the DynamoDB table
        response = dynamo_db.table.put_item(
            Item=item_data,
            ConditionExpression=condition_expression
        )
        
        return {
            'statusCode': 200,
            'body': 'Item created successfully'
        }
    except Exception as e:
        if hasattr(e, 'response') and e.response is not None and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return {
                'statusCode': 400,
                'body': 'Item already exists.'
            }
        return {
            'statusCode': 500,
            'body': 'Error creating item: ' + str(e)
        }

def get_item(dynamo_db: LambdaDynamoDBClass, item_id):
    try:
        # Get an item from the DynamoDB table
        response = dynamo_db.table.get_item(Key={'id': item_id})
        item = response.get('Item')

        if item:
            return {
                'statusCode': 200,
                'body': json.dumps(item)
            }
        else:
            return {
                'statusCode': 404,
                'body': 'Item not found'
            }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': 'Error getting item: ' + str(e)
        }

def update_item(dynamo_db: LambdaDynamoDBClass, item_id, item_data):
    try:
        # Get the current timestamp as the item's "modified" field
        item_data['modified'] = datetime.datetime.utcnow().isoformat()
    
        # Define the condition expression to check if the item already exists
        condition_expression = "attribute_exists(id)"
        
        # Define the UpdateExpression to set new values
        update_expression = "SET modified = :modified"
        
        # Define the values for the UpdateExpression
        expression_attribute_values = {
            ':modified': item_data['modified']
        }

        # Update the item only if it already exists
        response = dynamo_db.table.update_item(
            Key={'id': item_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression=condition_expression
        )
        return {
            'statusCode': 200,
            'body': 'Item updated successfully'
        }
    except Exception as e:
        if hasattr(e, 'response') and e.response is not None and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return {
                'statusCode': 404,
                'body': 'Item does not exist.'
            }
        return {
            'statusCode': 500,
            'body': 'Error updating item: ' + str(e)
        }

def delete_item(dynamo_db: LambdaDynamoDBClass, item_id):
    try:
        # Delete an item from the DynamoDB table
        response = dynamo_db.table.delete_item(Key={'id': item_id})
        return {
            'statusCode': 200,
            'body': 'Item deleted successfully'
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': 'Error deleting item: ' + str(e)
        }