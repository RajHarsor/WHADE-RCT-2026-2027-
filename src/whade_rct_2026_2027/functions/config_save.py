import json
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv


class ConfigSaver:
    def __init__(self):
        load_dotenv()

        self.aws_access_key_id = os.getenv('aws_access_key_id')
        self.aws_secret_access_key = os.getenv('aws_secret_access_key')
        self.region_name = 'us-east-1'
        self.s3_bucket_name = 'whade-rct-config'

        self.session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
        )

        self.s3 = self.session.client('s3')

    def save_config_to_s3(self, config_data, filename, folder):
        s3_key = f'{folder}/{filename}'

        try:
            if hasattr(config_data, 'write_csv'):
                # Polars DataFrame
                body = config_data.write_csv().encode('utf-8')
                content_type = 'text/csv'

            elif isinstance(config_data, (dict, list)):
                body = json.dumps(config_data, indent=2).encode('utf-8')
                content_type = 'application/json'

            elif isinstance(config_data, bytes):
                body = config_data
                content_type = 'application/octet-stream'

            elif isinstance(config_data, (str, Path)) and Path(config_data).is_file():
                # A local path to a real file, including .xlsx files.
                local_file_path = Path(config_data)

                with local_file_path.open('rb') as file:
                    body = file.read()

                if local_file_path.suffix.lower() == '.xlsx':
                    content_type = (
                        'application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet'
                    )
                elif local_file_path.suffix.lower() == '.csv':
                    content_type = 'text/csv'
                else:
                    content_type = 'application/octet-stream'

            else:
                raise ValueError(
                    'config_data must be a dictionary, list, bytes, Polars '
                    'DataFrame, or a valid local file path. '
                    f'Received: {type(config_data).__name__}'
                )

            self.s3.put_object(
                Bucket=self.s3_bucket_name,
                Key=s3_key,
                Body=body,
                ContentType=content_type,
            )

            print(
                f'Saved {len(body):,} bytes to '
                f's3://{self.s3_bucket_name}/{s3_key}'
            )

        except Exception as e:
            print(f'Error saving configuration to S3: {e}')
            raise

    def check_if_phase_config_exists(self, folder, filename):
        try:
            self.s3.head_object(
                Bucket=self.s3_bucket_name,
                Key=f'{folder}/{filename}',
            )
            return True

        except self.s3.exceptions.ClientError:
            return False

    def get_config_from_s3(self, folder, filename):
        try:
            response = self.s3.get_object(
                Bucket=self.s3_bucket_name,
                Key=f'{folder}/{filename}',
            )
            return response['Body'].read().decode('utf-8')

        except Exception as e:
            print(f'Error retrieving configuration from S3: {e}')
            return None
    
    def delete_phase_config(self, folder, filename):
        try:
            self.s3.delete_object(
                Bucket=self.s3_bucket_name,
                Key=f'{folder}/{filename}',
            )
            print(f'Deleted configuration for {folder} from S3.')
            return True

        except Exception as e:
            print(f'Error deleting configuration for {folder}/{filename} from S3: {e}')
            return False