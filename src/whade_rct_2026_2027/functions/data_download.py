import polars as pl
import boto3
from dotenv import load_dotenv, find_dotenv
import os
from io import BytesIO

# Load .env from the project root
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path)
    print(f"Loaded .env file from: {env_path}")
else:
    print("Warning: .env file not found. Make sure to set AWS credentials in the environment variables.")

class DataDownloader:
    def __init__(self):
        # Reload to ensure we have the latest values
        if env_path:
            load_dotenv(env_path)
        self.aws_access_key_id = os.getenv('aws_access_key_id')
        self.aws_secret_access_key = os.getenv('aws_secret_access_key')
        self.region_name = os.getenv('region', "us-east-1")
        self.s3_bucket_name = 'whade-rct-config'
        
        # Debug: Log if credentials are missing
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            print("WARNING: AWS credentials not found in environment variables!")

    def download_csv_from_s3(self, filename, folder):
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            print("ERROR: AWS credentials not configured. Please check your .env file.")
            return None
            
        Session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        s3 = Session.resource('s3')
        
        try:
            obj = s3.Object(self.s3_bucket_name, f"{folder}/{filename}")
            csv_data = obj.get()['Body'].read()
            df = pl.read_csv(BytesIO(csv_data))
            return df
        except Exception as e:
            error_msg = f"Error downloading CSV from S3: {str(e)}"
            print(error_msg)
            return None
    
    def verify_credentials(self):
        try:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name,
            )

            sts = session.client("sts")
            identity = sts.get_caller_identity()

            print(f"AWS account: {identity['Account']}")
            print(f"AWS ARN: {identity['Arn']}")
            print(f"AWS user ID: {identity['UserId']}")

        except Exception as e:
            print(f"AWS credential verification failed: {e}")
            
    def get_xlsx_from_s3(self, filename, folder):
        try:
            Session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name
            )
            s3 = Session.resource('s3')
            obj = s3.Object(self.s3_bucket_name, f"{folder}/{filename}")
            xlsx_data = obj.get()['Body'].read()
            return xlsx_data
        except Exception as e:
            print(f"Error downloading XLSX from S3: {str(e)}")
            return None
