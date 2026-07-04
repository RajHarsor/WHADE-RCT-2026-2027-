from nicegui import ui
from ..components import top_bar
import re
from datetime import date
from ..functions.data_download import *
import polars as pl

downloader = DataDownloader()

@ui.page('/download_view_aggregated_data')
def download_view_aggregated_data_page():
    
    def download_exercise_filtered_data(start_date, end_date):
        # if start_date or end_date is not datetime format convert them
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        
        try:
            df = downloader.download_csv_from_s3("daily_exercise_data.csv")
            
            # convert date column to datetime format
            df = df.with_columns(pl.col("date").str.strptime(pl.Date, format="%Y-%m-%d"))            
            # filter the dataframe based on the start and end dates
            filtered_df = df.filter((pl.col("date") >= start_date) & (pl.col("date") <= end_date))
            
            # download the filtered dataframe as a CSV file
            # Convert CSV string to bytes for ui.download
            csv_bytes = filtered_df.write_csv().encode()
            ui.download(csv_bytes, filename=f"exercise_filtered_data_{start_date}_{end_date}.csv")
        except Exception as e:
            ui.notify(f"Error downloading exercise filtered data: {str(e)}")
    
    def download_daily_filtered_data(start_date, end_date):
        # if start_date or end_date is not datetime format convert them
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        
        try:
            df = downloader.download_csv_from_s3("daily_fitbit_data.csv")
            
            # convert date column to datetime format
            df = df.with_columns(pl.col("date").str.strptime(pl.Date, format="%Y-%m-%d"))            
            # filter the dataframe based on the start and end dates
            filtered_df = df.filter((pl.col("date") >= start_date) & (pl.col("date") <= end_date))
            
            # download the filtered dataframe as a CSV file
            # Convert CSV string to bytes for ui.download
            csv_bytes = filtered_df.write_csv().encode()
            ui.download(csv_bytes, filename=f"daily_filtered_data_{start_date}_{end_date}.csv")
        except Exception as e:
            ui.notify(f"Error downloading daily filtered data: {str(e)}")
    
    top_bar.top_bar("Download/View Aggregated Data")

    with ui.column().classes('w-full justify-center items-center'):
        with ui.input(label="Start Date (YYYY-MM-DD)", validation={'Must be a valid date (YYYY-MM-DD)': lambda x: bool(re.match(r'^\d{4}-\d{2}-\d{2}$', x))}).props('clearable').classes('w-full') as start_date_input:
            with ui.menu().props('no-parent-event') as menu:
                with ui.date().bind_value(start_date_input):
                    with ui.row().classes('justify-end'):
                        ui.button("Select", on_click=menu.close).props('flat')
            with start_date_input.add_slot('append'):
                ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
        with ui.input(label="End Date (YYYY-MM-DD)", validation={'Must be a valid date (YYYY-MM-DD)': lambda x: bool(re.match(r'^\d{4}-\d{2}-\d{2}$', x))}).props('clearable').classes('w-full') as end_date_input:
            with ui.menu().props('no-parent-event') as menu:
                with ui.date().bind_value(end_date_input):
                    with ui.row().classes('justify-end'):
                        ui.button("Select", on_click=menu.close).props('flat')
            with end_date_input.add_slot('append'):
                ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
        
    with ui.row().classes('w-full justify-center items-center mt-4'):
        ui.button("Download Daily Aggregated Data", on_click=lambda: download_daily_filtered_data(start_date_input.value, end_date_input.value)).classes('w-1/3')
        # TODO: Placeholder for exercise data download – currently not implemented
        ui.button("Download Exercise Data", on_click=lambda: download_exercise_filtered_data(start_date_input.value, end_date_input.value)).classes('w-1/3')