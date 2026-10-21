import boto3
import os
from dotenv import load_dotenv
from ..functions.env_initialization import read_env_variables


def send_test_sms(participant_phone_number, message):
    """
    Send a test SMS to the specified phone number using AWS SNS.
    
    Args:
        participant_phone_number (str): The participant's phone number in E.164 format.
        message (str): The message to send.
    
    Returns:
        bool: True if the SMS was sent successfully, False otherwise.
        message (str): Success or error message.
    """
    env_vars = read_env_variables()
    
    Session = boto3.Session(
        aws_access_key_id=env_vars['aws_access_key_id'],
        aws_secret_access_key=env_vars['aws_secret_access_key'],
        region_name=env_vars['region']
    )
    
    sns = Session.client('sns')
    
    try:
        sns.publish(
            PhoneNumber=participant_phone_number,
            Message=message
        )
        return True, "SMS sent successfully."
    except Exception as e:
        print(f"Error sending test SMS: {e}")
        return False, f"Error sending test SMS: {e}"