import boto3
import json
import os
from io import BytesIO
from dotenv import load_dotenv

class ConfigSaver:
    def __init__(self):
        load_dotenv()
        self.aws_access_key_id = os.getenv('aws_access_key_id')
        self.aws_secret_access_key = os.getenv('aws_secret_access_key')
        self.region_name = "us-east-1"
        self.s3_bucket_name = 'whade-rct-config'
        
    def save_config_to_s3(self, config_data, filename, folder):
        Session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        s3 = Session.resource('s3')
        
        try:
            if hasattr(config_data, 'write_csv'):
                body = config_data.write_csv().encode('utf-8')
            elif isinstance(config_data, (dict, list)):
                body = json.dumps(config_data, indent=2).encode('utf-8')
            elif isinstance(config_data, bytes):
                body = config_data
            else:
                body = str(config_data).encode('utf-8')

            s3.Object(self.s3_bucket_name, f"{folder}/{filename}").put(Body=body)
            print(f"Configuration saved to S3 bucket '{self.s3_bucket_name}' with filename '{filename}'")
        except Exception as e:
            print(f"Error saving configuration to S3: {str(e)}")

    def check_if_phase_config_exists(self, folder, filename):
        Session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        s3 = Session.resource('s3')
        try:
            s3.Object(self.s3_bucket_name, f"{folder}/{filename}").load()
            return True
        except Exception as e:
            return False
    
    def get_config_from_s3(self, folder, filename):
        Session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        s3 = Session.resource('s3')
        try:
            obj = s3.Object(self.s3_bucket_name, f"{folder}/{filename}")
            config_data = obj.get()['Body'].read().decode('utf-8')
            return config_data
        except Exception as e:
            print(f"Error retrieving configuration from S3: {str(e)}")
            return None