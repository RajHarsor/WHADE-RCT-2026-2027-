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
                "start": {
                    "date": {
                        "year": start_date.year,
                        "month": start_date.month,
                        "day": start_date.day,
                    },
                    "time": {
                        "hours": 0,
                        "minutes": 0,
                        "seconds": 0,
                    }
                },
                "end": {
                    "date": {
                        "year": end_date.year,
                        "month": end_date.month,
                        "day": end_date.day,
                    },
                    "time": {
                        "hours": 0,
                        "minutes": 0,
                        "seconds": 0,
                    }
                },
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
                    "restingHeartRate_recordingMethod": point.get("dataSource", {}).get('recordingMethod', 'unknown'),
                    "restingHeartRate_calculationMethod": resting_heart_rate.get("dailyRestingHeartRateMetadata", {}).get("calculationMethod", "unknown"),
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
    
    def aggregate_sedentary_period_over_time(self, participant_id, creds, start_date, end_date):
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date() + timedelta(days=1)
        
        url = "https://health.googleapis.com/v4/users/me/dataTypes/sedentary-period/dataPoints:dailyRollUp"
        body = {
            "range": {
                "start": {
                    "date": {
                        "year": start_date.year,
                        "month": start_date.month,
                        "day": start_date.day,
                    },
                    "time": {
                        "hours": 0,
                        "minutes": 0,
                        "seconds": 0,
                    }
                },
                "end": {
                    "date": {
                        "year": end_date.year,
                        "month": end_date.month,
                        "day": end_date.day,
                    },
                    "time": {
                        "hours": 0,
                        "minutes": 0,
                        "seconds": 0,
                    }
                },
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
            logging.error(f"Error fetching sedentary periods data for participant {participant_id}: {response.text}")
            response.raise_for_status()
            
        data = response.json()
        results = []
        for point in data.get("rollupDataPoints", []):
            st = point.get("civilStartTime", {}).get("date", {})
            date = f"{st['year']}-{st['month']:02d}-{st['day']:02d}"
            sedentary_minutes = point.get("sedentaryMinutes", {}).get("durationSum", 0) / 60
            results.append({"date": date, "sedentary_minutes": sedentary_minutes})
        
        df = polars.DataFrame(results)
        return results, df
    
    def aggregate_daily_heart_rate_zones(self, participant_id, creds, start_date, end_date):
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date() + timedelta(days=1)

        def extract_point_date(point):
            date_value = point.get("date") or point.get("dailyHeartRateZones", {}).get("date")
            if isinstance(date_value, dict) and {"year", "month", "day"}.issubset(date_value):
                return datetime(
                    date_value["year"],
                    date_value["month"],
                    date_value["day"],
                ).date()

            if isinstance(date_value, dict):
                nested_date = date_value.get("date") or date_value.get("localDate")
                if isinstance(nested_date, dict) and {"year", "month", "day"}.issubset(nested_date):
                    return datetime(
                        nested_date["year"],
                        nested_date["month"],
                        nested_date["day"],
                    ).date()

                iso_date = date_value.get("value") or date_value.get("dateString")
                if isinstance(iso_date, str):
                    return datetime.strptime(iso_date[:10], "%Y-%m-%d").date()

            if isinstance(date_value, str):
                return datetime.strptime(date_value[:10], "%Y-%m-%d").date()

            civil_date = point.get("civilStartTime", {}).get("date", {})
            if isinstance(civil_date, dict) and {"year", "month", "day"}.issubset(civil_date):
                return datetime(
                    civil_date["year"],
                    civil_date["month"],
                    civil_date["day"],
                ).date()

            return None

        def build_zone_row(point, point_date):
            zones_data = point.get("dailyHeartRateZones", {}).get("heartRateZones", [])
            row = {
                "date": point_date.isoformat() if point_date else None,
            }

            for zone in zones_data:
                zone_name = zone.get("heartRateZoneType") or zone.get("name")
                if not zone_name:
                    continue

                prefix = zone_name.lower()
                if "duration" in zone and zone["duration"] is not None:
                    row[f"{prefix}_minutes"] = zone["duration"] / 60
                if "minBeatsPerMinute" in zone and zone["minBeatsPerMinute"] is not None:
                    row[f"{prefix}_min_bpm"] = int(zone["minBeatsPerMinute"])
                if "maxBeatsPerMinute" in zone and zone["maxBeatsPerMinute"] is not None:
                    row[f"{prefix}_max_bpm"] = int(zone["maxBeatsPerMinute"])

            return row
        
        url = "https://health.googleapis.com/v4/users/me/dataTypes/daily-heart-rate-zones/dataPoints"
        
        headers = self.get_headers(creds)
        response = requests.get(url, headers=headers)

        if response.status_code == 401:
            creds = self._refresh_credentials(participant_id, creds)
            headers = self.get_headers(creds)
            response = requests.get(url, headers=headers)
        
        if not response.ok:
            logging.error(f"Error fetching daily heart rate zones data for participant {participant_id}: {response.text}")
            response.raise_for_status()
            
        data = response.json()
        results = []
        for point in data.get("dataPoints", []):
            point_date = extract_point_date(point)
            if point_date is None:
                logging.warning(
                    "Skipping daily heart rate zone point with unexpected date shape for participant %s: %s",
                    participant_id,
                    point,
                )
                continue

            if start_date <= point_date <= end_date:
                results.append(build_zone_row(point, point_date))

        if not results and data.get("dataPoints"):
            logging.warning(
                "Daily heart rate zones returned no rows for participant %s within %s to %s; returning raw points because the API is not providing usable calendar dates for this data type.",
                participant_id,
                start_date,
                end_date,
            )

            for point in data.get("dataPoints", []):
                point_date = extract_point_date(point)
                results.append(build_zone_row(point, point_date))

        df = polars.DataFrame(results)
        return results, df
    
    def aggregate_active_minutes_over_time(self, participant_id, creds, start_date, end_date):
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date() + timedelta(days=1)
        
        # check if start_date to end_date is greater than 14 days, otherwise we have to split into multiple requests because the API has a max range of 14 days for this endpoint

        url = "https://health.googleapis.com/v4/users/me/dataTypes/active-minutes/dataPoints:dailyRollUp"
        body = {
            "range": {
                "start": {
                    "date": {
                        "year": start_date.year,
                        "month": start_date.month,
                        "day": start_date.day,
                    },
                    "time": {
                        "hours": 0,
                        "minutes": 0,
                        "seconds": 0,
                    }
                },
                "end": {
                    "date": {
                        "year": end_date.year,
                        "month": end_date.month,
                        "day": end_date.day,
                    },
                    "time": {
                        "hours": 0,
                        "minutes": 0,
                        "seconds": 0,
                    }
                },
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
            logging.error(f"Error fetching active minutes data for participant {participant_id}: {response.text}")
            response.raise_for_status()
            
        data = response.json()
        results = []
        for point in data.get("rollupDataPoints", []):
            st = point.get("civilStartTime", {}).get("date", {})
            date = f"{st['year']}-{st['month']:02d}-{st['day']:02d}"
            activity_minutes = {
                "light_active_minutes": 0,
                "moderate_active_minutes": 0,
                "vigorous_active_minutes": 0,
            }

            for activity_level in point.get("activeMinutes", {}).get("activeMinutesRollupByActivityLevel", []):
                level_name = activity_level.get("activityLevel", "").upper()
                level_minutes = float(activity_level.get("activeMinutesSum", 0))

                if level_name == "LIGHT":
                    activity_minutes["light_active_minutes"] = level_minutes
                elif level_name == "MODERATE":
                    activity_minutes["moderate_active_minutes"] = level_minutes
                elif level_name == "VIGOROUS":
                    activity_minutes["vigorous_active_minutes"] = level_minutes

            total_active_minutes = sum(activity_minutes.values())
            results.append({
                "date": date,
                "active_minutes": total_active_minutes,
                **activity_minutes,
            })
            
        df = polars.DataFrame(results)
        return data, df

    def get_intraday_heartrate(self, participant_id, creds, date):
        if isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d").date()

        url = "https://health.googleapis.com/v4/users/me/dataTypes/heart-rate/dataPoints"
        
        headers = self.get_headers(creds)
        params = {"pageSize": 10000}
        data = {"dataPoints": []}
        page_token = None

        while True:
            if page_token:
                params["pageToken"] = page_token
            elif "pageToken" in params:
                params.pop("pageToken")

            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 401:
                creds = self._refresh_credentials(participant_id, creds)
                headers = self.get_headers(creds)
                response = requests.get(url, headers=headers, params=params)

            if not response.ok:
                logging.error(f"Error fetching intraday heart rate data for participant {participant_id} on {date}: {response.text}")
                response.raise_for_status()

            page_data = response.json()
            data["dataPoints"].extend(page_data.get("dataPoints", []))

            page_token = page_data.get("nextPageToken")
            if not page_token:
                break

        results = []
        for point in data.get("dataPoints", []):
            heart_rate_value = point.get("heartRate", point)
            sample_time = heart_rate_value.get("sampleTime", {})
            timestamp_value = sample_time.get("physicalTime") or heart_rate_value.get("timestamp")
            if timestamp_value is None:
                logging.warning(
                    "Skipping intraday heart rate point with missing timestamp for participant %s on %s: %s",
                    participant_id,
                    date,
                    point,
                )
                continue

            try:
                timestamp = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
            except ValueError as e:
                logging.warning(
                    "Skipping intraday heart rate point with invalid timestamp format for participant %s on %s: %s; error: %s",
                    participant_id,
                    date,
                    point,
                    e,
                )
                continue

            if timestamp.date() != date:
                continue

            results.append({
                "timestamp": timestamp.isoformat(),
                "heart_rate": heart_rate_value.get("beatsPerMinute", 0),
            })

        df = polars.DataFrame(results)
        return data, df
    
    def get_all_dfs_and_join(self, participant_id, creds, start_date, end_date):
        start_date_input = start_date
        end_date_input = end_date

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        steps_df = self.aggregate_steps_over_time(participant_id, creds, start_date_input, end_date_input)
        resting_hr_df, _ = self.restingHeartRate_over_time(participant_id, creds, start_date_input, end_date_input)
        _, sedentary_df = self.aggregate_sedentary_period_over_time(participant_id, creds, start_date_input, end_date_input)
        
        # check if start_date to end_date is greater than 14 days, otherwise we have to split into multiple requests because the API has a max range of 14 days for this endpoint
        end_date_exclusive = end_date + timedelta(days=1)
        if (end_date_exclusive - start_date).days > 14:
            active_minutes_df = polars.DataFrame()
            current_start = start_date
            while current_start < end_date_exclusive:
                current_end = min(current_start + timedelta(days=14), end_date_exclusive)
                _, current_active_minutes_df = self.aggregate_active_minutes_over_time(participant_id, creds, current_start, current_end)
                active_minutes_df = active_minutes_df.vstack(current_active_minutes_df)
                current_start = current_end
        else:
            _, active_minutes_df = self.aggregate_active_minutes_over_time(participant_id, creds, start_date_input, end_date_input)
        
        # Join all dataframes on date
        combined_df = (
            steps_df.join(resting_hr_df, on="date", how="outer", coalesce=True)
            .join(sedentary_df, on="date", how="outer", coalesce=True)
            .join(active_minutes_df, on="date", how="outer", coalesce=True)
        )
        return combined_df, steps_df, resting_hr_df, sedentary_df, active_minutes_df
    
    def get_exercise_data(self, participant_id, creds, start_date, end_date):
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        url = "https://health.googleapis.com/v4/users/me/dataTypes/exercise/dataPoints"
        end_date_exclusive = end_date + timedelta(days=1)
        filter_expression = (
            f'exercise.interval.civil_start_time >= "{start_date.isoformat()}" AND '
            f'exercise.interval.civil_start_time < "{end_date_exclusive.isoformat()}"'
        )
        
        headers = self.get_headers(creds)
        params = {"pageSize": 25, "filter": filter_expression}
        data = {"dataPoints": []}
        page_token = None
        
        while True:
            if page_token:
                params["pageToken"] = page_token
            elif "pageToken" in params:
                params.pop("pageToken")

            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 401:
                creds = self._refresh_credentials(participant_id, creds)
                headers = self.get_headers(creds)
                response = requests.get(url, headers=headers, params=params)

            if not response.ok:
                logging.error(f"Error fetching exercise data for participant {participant_id} between {start_date} and {end_date}: {response.text}")
                response.raise_for_status()

            page_data = response.json()
            data["dataPoints"].extend(page_data.get("dataPoints", []))

            page_token = page_data.get("nextPageToken")
            if not page_token:
                break
        results = []

        def extract_exercise_date(point):
            exercise = point.get("exercise", {})
            interval = exercise.get("interval", {})

            civil_time = interval.get("civilStartTime") or interval.get("civil_start_time")
            if isinstance(civil_time, dict):
                date_value = civil_time.get("date", {})
                if isinstance(date_value, dict):
                    year = date_value.get("year", 0)
                    month = date_value.get("month", 0)
                    day = date_value.get("day", 0)
                    if year and month and day:
                        return datetime(year, month, day).date()

            start_time = interval.get("startTime") or interval.get("start_time")
            if isinstance(start_time, str):
                try:
                    return datetime.fromisoformat(start_time.replace("Z", "+00:00")).date()
                except ValueError:
                    return None

            return None

        for point in data.get("dataPoints", []):
            point_date = extract_exercise_date(point)
            if point_date is None:
                logging.warning(
                    "Skipping exercise point with missing or malformed date for participant %s between %s and %s: %s",
                    participant_id,
                    start_date,
                    end_date,
                    point,
                )
                continue

            exercise_recording_method = point.get("dataSource", {}).get('recordingMethod', 'unknown')
            exercise_type = point.get("exercise", {}).get("exerciseType", "unknown")
            exercise_duration_seconds = point.get("exercise", {}).get("activeDuration", 0)
            if isinstance(exercise_duration_seconds, str) and exercise_duration_seconds.endswith("s"):
                try:
                    exercise_duration_seconds = float(exercise_duration_seconds[:-1])
                except ValueError:
                    exercise_duration_seconds = 0
            exercise_start_time = point.get("exercise", {}).get("interval", {}).get("startTime", {})
            exercise_end_time = point.get("exercise", {}).get("interval", {}).get("endTime", {})
            results.append({
                "date": point_date.isoformat(),
                "exercise_recording_method": str(exercise_recording_method),
                "exercise_type": str(exercise_type),
                "exercise_duration_seconds": exercise_duration_seconds,
                "exercise_start_time": exercise_start_time,
                "exercise_end_time": exercise_end_time,
            })
        
        exercise_df = polars.DataFrame(results)
        return exercise_df, data
