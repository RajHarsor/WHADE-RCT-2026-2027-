import boto3
from ..functions.env_initialization import read_env_variables


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
    table = dynamodb.Table(env_vars['insight_p3_table_name'])
    
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
