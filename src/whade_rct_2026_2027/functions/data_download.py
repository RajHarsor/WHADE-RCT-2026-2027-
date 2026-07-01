import polars as pl
import boto3
from dotenv import load_dotenv
import os
from io import BytesIO

class DataDownloader:
    def __init__(self):
        load_dotenv()
        self.aws_access_key_id = os.getenv('aws_access_key_id')
        self.aws_secret_access_key = os.getenv('aws_secret_access_key')
        self.region_name = "us-east-1"
        self.s3_bucket_name = 'whade-rct-config'

    def download_csv_from_s3(self, filename):
        Session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        s3 = Session.resource('s3')
        
        try:
            obj = s3.Object(self.s3_bucket_name, filename)
            csv_data = obj.get()['Body'].read()
            df = pl.read_csv(BytesIO(csv_data))
            return df
        except Exception as e:
            print(f"Error downloading CSV from S3: {str(e)}")
            return None