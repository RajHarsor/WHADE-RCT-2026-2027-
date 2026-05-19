import time
import requests
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import os
from dotenv import load_dotenv
from decimal import Decimal
import boto3
import polars
import logging

logging.basicConfig(filename='whade_rct_api.log', format='%(asctime)s - %(levelname)s - %(message)s', level = logging.INFO)

BASE_URL = "https://health.googleapis.com/v4"

SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
]
class FitbitAuth:
    def __init__(self):
        load_dotenv()

        ## Initialize AWS credentials
        self.aws_access_key_id = os.getenv('aws_access_key_id')
        self.aws_secret_access_key = os.getenv('aws_secret_access_key')
        self.aws_table_name = "Project_WHADE_RCT"
        self.region_name = "us-east-1"
    
    def get_credentials_file(self):
        if not os.path.exists('credentials.json'):
            Session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name
            )
            s3 = Session.client('s3')
            try:
                s3.download_file('whade-rct-config', 'credentials.json', 'credentials.json')
                logging.info("Credentials file downloaded successfully from S3.")
            except Exception as e:
                logging.error(f"Error downloading credentials file from S3: {e}")
                raise e

    def generate_auth_link(self):
        try:
            self.get_credentials_file()
            flow = Flow.from_client_secrets_file(
                'credentials.json',
                scopes=SCOPES,
                redirect_uri="https://drarigo.wordpress.com/"
            )

            auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
            logging.info("Authorization URL generated successfully.")
        except Exception as e:
            logging.error(f"Error generating authorization URL: {e}")
            raise e
        return auth_url, flow
    
    def save_tokens(self, participant_id, phase, week_0_start_date, redirect_url, flow):
        try:
            flow.fetch_token(authorization_response=redirect_url)
            creds = flow.credentials
            
            # Parse the tokens and other relevant info
            token = creds.token
            refresh_token = creds.refresh_token
            token_uri = creds.token_uri
            client_id = creds.client_id
            client_secret = creds.client_secret
            scopes = creds.scopes
            expiry = creds.expiry
            
            #dynamodb save
            Session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name
            )
            
            dynamodb = Session.resource('dynamodb')
            table = dynamodb.Table(self.aws_table_name)
            
            table.put_item(
                Item={
                    'participant_id': participant_id,
                    'phase': phase,
                    'week_0_start_date': week_0_start_date,
                    'token': token,
                    'refresh_token': refresh_token,
                    'token_uri': token_uri,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'scopes': scopes,
                    'expiry': Decimal(str(expiry.timestamp())) # Store as timestamp in DynamoDB
                }
            )
            logging.info(f"Tokens saved to DynamoDB successfully for participant {participant_id}.")
            e = None
        except Exception as e:
            logging.error(f"Error saving tokens to DynamoDB for participant {participant_id}: {e}")
            return e

    def get_credentials(self, participant_id):
        Session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        
        dynamodb = Session.resource('dynamodb')
        table = dynamodb.Table(self.aws_table_name)
        
        response = table.get_item(Key={'participant_id': participant_id})
        item = response.get('Item')
        print(item)
        
        if not item:
            logging.error(f"No credentials found for participant {participant_id}")
            return None
        
        creds = Credentials(
            token=item['token'],
            refresh_token=item['refresh_token'],
            token_uri=item['token_uri'],
            client_id=item['client_id'],
            client_secret=item['client_secret'],
            scopes=item['scopes'],
            expiry=datetime.utcfromtimestamp(float(item['expiry'])) if item.get('expiry') else None
        )
        
        # Check if token is expired and refresh if necessary
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_tokens_to_dynamodb(participant_id, {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes,
                    'expiry': Decimal(str(creds.expiry.timestamp()))
                })
                logging.info(f"Tokens for participant {participant_id} refreshed successfully.")
            except Exception as e:
                logging.error(f"Error refreshing tokens for participant {participant_id}: {e}")
                return None
        
        return creds

    def get_headers(self, creds):
        return {
            "Authorization": f"Bearer {creds.token}"
        }

    def _refresh_credentials(self, participant_id, creds):
        if not creds.refresh_token:
            return creds

        creds.refresh(Request())
        self._save_tokens_to_dynamodb(participant_id, {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
            'expiry': Decimal(str(creds.expiry.timestamp())) if creds.expiry else None,
        })
        return creds

    def aggregate_steps_over_time(self, participant_id, creds, start_date, end_date):
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date() 
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date() + timedelta(days=1)
        url = "https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp"
        body = {
            "range": {
                "start":
                    {
                        "date": {
                            "year": start_date.year,
                            "month": start_date.month,
                            "day": start_date.day
                        }
                    },
                "end": {
                    "date": {
                        "year": end_date.year,
                        "month": end_date.month,
                        "day": end_date.day
                    }
                }
            },
            "windowSizeDays": 1,
        }
        
        headers = self.get_headers(creds)
        response = requests.post(url, json=body, headers=headers)

        if response.status_code == 401:
            creds = self._refresh_credentials(participant_id, creds)
            headers = self.get_headers(creds)
            response = requests.post(url, json=body, headers=headers)
        
        if not response.ok:
            logging.error(f"Error fetching steps data for participant {participant_id}: {response.text}")
            response.raise_for_status()
            
        data = response.json()
        results = []
        for point in data.get("rollupDataPoints", []):
            st = point.get("civilStartTime", {}).get("date", {})
            date = f"{st['year']}-{st['month']:02d}-{st['day']:02d}"
            steps = point.get("steps", {}).get("countSum", 0)
            results.append({"date": date, "steps": steps})
        
        # convert to df
        df = polars.DataFrame(results)

        return df
    
    def restingHeartRate_over_time(self, participant_id, creds, start_date, end_date):
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            
        url = "https://health.googleapis.com/v4/users/me/dataTypes/daily-resting-heart-rate/dataPoints"
        
        headers = self.get_headers(creds)
        response = requests.get(url, headers=headers)

        if response.status_code == 401:
            creds = self._refresh_credentials(participant_id, creds)
            headers = self.get_headers(creds)
            response = requests.get(url, headers=headers)
        
        if not response.ok:
            logging.error(f"Error fetching resting heart rate data for participant {participant_id}: {response.text}")
            response.raise_for_status()
            
        data = response.json()
        results = []
        for point in data.get("dataPoints", []):
            resting_heart_rate = point.get("dailyRestingHeartRate", point)
            date_value = resting_heart_rate.get("date", {})
            point_date = datetime(
                date_value["year"],
                date_value["month"],
                date_value["day"],
            ).date()

            if start_date <= point_date <= end_date:
                results.append({
                    "date": f"{point_date.year}-{point_date.month:02d}-{point_date.day:02d}",
                    "restingHeartRate": resting_heart_rate.get("beatsPerMinute", 0),
                })

        df = polars.DataFrame(results)
        return df, data

    def _save_tokens_to_dynamodb(self, participant_id, token_data):
        Session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        
        dynamodb = Session.resource('dynamodb')
        table = dynamodb.Table(self.aws_table_name)
        
        try:
            table.update_item(
                Key={'participant_id': participant_id},
                UpdateExpression="set #token=:t, refresh_token=:rt, token_uri=:tu, client_id=:ci, client_secret=:cs, scopes=:s, expiry=:e",
                ExpressionAttributeNames={
                    '#token': 'token'
                },
                ExpressionAttributeValues={
                    ':t': token_data['token'],
                    ':rt': token_data['refresh_token'],
                    ':tu': token_data['token_uri'],
                    ':ci': token_data['client_id'],
                    ':cs': token_data['client_secret'],
                    ':s': token_data['scopes'],
                    ':e': token_data['expiry']
                }
            )
        except Exception as e:
            logging.error(f"Error saving tokens to DynamoDB for participant {participant_id}: {e}")
            raise e