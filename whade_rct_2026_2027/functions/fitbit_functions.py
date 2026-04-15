import os
import fitbit
import polars as pl
from dotenv import load_dotenv
from decimal import Decimal
import boto3
import logging

logging.basicConfig(filename='project_pace_api.log', format='%(asctime)s - %(levelname)s - %(message)s', level = logging.INFO)

class FitbitAuthSimple:
    def __init__(self):
        load_dotenv()

        ## Initialize Fitbit API credentials
        self.client_id = os.getenv('FITBIT_CLIENT_ID')
        self.client_secret = os.getenv('FITBIT_CLIENT_SECRET')
        self.redirect_uri = os.getenv('FITBIT_REDIRECT_URI')

        ## Initialize AWS credentials
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_table_name = "Project_WHADE_RCT"
        self.region_name = "us-east-1"

    def get_auth_url(self):
        """Generate authorization link for a participant

        Returns:
            str: The authorization URL that the user should visit to authorize the application
        """

        logging.info("get_auth_link called to generate authorization URL")

        client = fitbit.Fitbit(
            self.client_id,
            self.client_secret,
            redirect_uri=self.redirect_uri,
            oauth2=True
        )
        url, _ = client.client.authorize_token_url(
            scope=['activity', 'sleep', 'heart']
        )
        logging.info(f"Generated authorization URL: {url}.")
        return url

    def save_token_from_code(self, user_id, auth_code):
        """Save token using auth code from URL

        Args:
            user_id (str): The ID of the user
            auth_code (str): The authorization code received from Fitbit after user authorization

        Returns:
            dict: The access token and refresh token for the user
        """
        logging.info(f"save_token_from_code called for user {user_id} with auth code: {auth_code}")
        client = fitbit.Fitbit(
            self.client_id,
            self.client_secret,
            redirect_uri=self.redirect_uri,
            oauth2=True
        )
        tokens = client.client.fetch_access_token(auth_code)
        logging.info(f"Tokens received for user {user_id}: {tokens}")

        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']
        expires_in = tokens['expires_in']
        expires_at = Decimal(str(tokens['expires_at'])) # this is a float
        scope = tokens['scope']
        token_type = tokens['token_type']
        token_user_id = tokens['user_id']

        # Save info to dynamodb
        Session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )

        dynamodb = Session.resource('dynamodb')
        table = dynamodb.Table(self.aws_table_name)

        table.put_item(
            Item={
                'user_id': user_id,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': expires_in,
                'expires_at': expires_at,
                'scope': scope,
                'token_type': token_type,
                'user_id': token_user_id
            }
        )
    
    def _save_tokens_to_dynamodb(self, participant_id, tokens):
        """Save refreshed tokens to AWS DynamoDB

        Args:
            participant_id (str): The ID of the participant
            tokens (dict): The refreshed tokens
        """
        logging.info(f"_save_tokens_to_dynamodb called for participant {participant_id} with tokens: {tokens}")
        
        Session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        
        dynamodb = Session.resource("dynamodb")
        table = dynamodb.Table(self.aws_table_name)
        
        table.update_item(
            Key={'participant_id': participant_id},
            UpdateExpression="SET access_token = :access_token, refresh_token = :refresh_token, expires_in = :expires_in, expires_at = :expires_at, #scope_attr = :scope, token_type = :token_type, user_id = :user_id",
            ExpressionAttributeNames={
                '#scope_attr': 'scope'
            },
            ExpressionAttributeValues={
                ':access_token': tokens['access_token'],
                ':refresh_token': tokens['refresh_token'],
                ':expires_in': tokens['expires_in'],
                ':expires_at': Decimal(str(tokens['expires_at'])),
                ':scope': tokens['scope'],
                ':token_type': tokens['token_type'],
                ':user_id': tokens['user_id']
            }
        )
        print(f"Tokens for participant {participant_id} updated in DynamoDB.")
        logging.info(f"Tokens with following information {tokens} for participant {participant_id} updated in DynamoDB.")