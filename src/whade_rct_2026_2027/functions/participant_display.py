import boto3
import os
import dotenv
from ..functions.env_initialization import read_env_variables

table_name = "Project_WHADE_RCT"

def get_user_info(participant_id):
    """
    Retrieve user information from the AWS DynamoDB table.
    
    Args:
        participant_id (int): The participant ID.
    
    Returns:
        dict: User information if found, None otherwise.
    """
    env_vars = read_env_variables()
    
    Session = boto3.Session(
        aws_access_key_id=env_vars['aws_access_key_id'],
        aws_secret_access_key=env_vars['aws_secret_access_key'],
        region_name=env_vars['region']
    )
    dynamodb = Session.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    try:
        response = table.get_item(
            Key={
                'participant_id': int(participant_id)
            }
        )
        return response.get('Item', None), 'Error: User not found.'
    except Exception as e:
        print(f"Error retrieving user from database: {e}")
        return None, f"Error retrieving user from database: {e}"

def get_all_participant_ids():
    """
    Scan the AWS DynamoDB table for every participant_id.

    Returns:
        set: Participant IDs present in the table.
        None: If the scan failed, so callers can tell "empty" from "unknown".
    """
    env_vars = read_env_variables()

    Session = boto3.Session(
        aws_access_key_id=env_vars['aws_access_key_id'],
        aws_secret_access_key=env_vars['aws_secret_access_key'],
        region_name=env_vars['region']
    )
    dynamodb = Session.resource('dynamodb')
    table = dynamodb.Table(table_name)

    participant_ids = set()
    scan_kwargs = {'ProjectionExpression': 'participant_id'}

    try:
        while True:
            response = table.scan(**scan_kwargs)
            participant_ids.update(
                int(item['participant_id'])
                for item in response.get('Items', [])
            )
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
            scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
        return participant_ids
    except Exception as e:
        print(f"Error scanning participants from database: {e}")
        return None

def update_user_info(participant_id, attribute_name, new_value):
    """
    Update user information in the AWS DynamoDB table.
    
    Args:
        participant_id (int): The participant ID.
        attribute_name (str): The attribute name to update.
        new_value: The new value for the attribute.
    
    Returns:
        bool: True if the update was successful, False otherwise.
        message (str): Success or error message.
    """
    env_vars = read_env_variables()
    
    Session = boto3.Session(
        aws_access_key_id=env_vars['aws_access_key_id'],
        aws_secret_access_key=env_vars['aws_secret_access_key'],
        region_name=env_vars['region']
    )
    dynamodb = Session.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    try: 
        table.update_item(
            Key={
                'participant_id': int(participant_id)
            },
            UpdateExpression=f'SET {attribute_name} = :val',
            ExpressionAttributeValues={
                ':val': new_value
            }
        )
        return True, "User information updated successfully."
    except Exception as e:
        print(f"Error updating user in database: {e}")
        return False, f"Error updating user in database: {e}"

def delete_user_from_database(participant_id):
    """
    Delete a user from the AWS DynamoDB table.
    
    Args:
        participant_id (int): The participant ID.
    Returns:
        bool: True if the deletion was successful, False otherwise.
        message (str): Success or error message.
    """
    env_vars = read_env_variables()
    
    Session = boto3.Session(
        aws_access_key_id=env_vars['aws_access_key_id'],
        aws_secret_access_key=env_vars['aws_secret_access_key'],
        region_name=env_vars['region']
    )
    dynamodb = Session.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    try:
        table.delete_item(
            Key={
                'participant_id': int(participant_id)
            }
        )
        return True, "User deleted successfully."
    except Exception as e:
        print(f"Error deleting user from database: {e}")
        return False, f"Error deleting user from database: {e}"