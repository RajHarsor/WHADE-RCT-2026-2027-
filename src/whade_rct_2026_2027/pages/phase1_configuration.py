from nicegui import ui
import random
from ..components import top_bar
import polars as pl
import json
from io import BytesIO
from ..functions.config_save import ConfigSaver

config_saver = ConfigSaver()

@ui.page('/phase1')
def phase1_configuration_page():
    page_state = {
        'baseline_df': None,
        'coach_availability_df': None,
    }
    
    async def handle_baselinedata_file_upload(event):
        # Read in the uploaded file (csv) and save it as a polars dataframe in the "data" directory with the original filename
        uploaded_bytes = await event.file.read()
        page_state['baseline_df'] = pl.read_csv(BytesIO(uploaded_bytes))
        ui.notify(f"Baseline CSV uploaded: {event.file.name}", color="green")
        return page_state['baseline_df']
    
    async def handle_coach_availability_file_upload(event):
        # Read in the uploaded file (csv) and save it as a polars dataframe in the "data" directory with the original filename
        uploaded_bytes = await event.file.read()
        page_state['coach_availability_df'] = pl.read_csv(BytesIO(uploaded_bytes))
        ui.notify(f"Coach availability CSV uploaded: {event.file.name}", color="green")
        return page_state['coach_availability_df']
    
    def save_phase1_configuration():
        # Get values from the input fields
        seed = seed_box.value
        start_date = start_date_input.value
        num_participants = num_participants_input.value
        num_participants_partner = num_participants_partner_input.value
        
        # Validate inputs
        if not seed or not start_date or not num_participants or not num_participants_partner:
            ui.notify("Please fill in all fields", color="red")
            return
        
        # Save the configuration to a JSON file (or you can choose another format)
        config_data = {
            "seed": seed,
            "start_date": start_date,
            "num_participants": num_participants,
            "num_participants_partner": num_participants_partner,
        }
        
        if page_state['coach_availability_df'] is None or page_state['baseline_df'] is None:
            ui.notify("Please upload both CSV files before saving", color="red")
            return

        config_saver.save_config_to_s3(config_data, "phase1_configuration.json", "phase1")
        config_saver.save_config_to_s3(page_state['coach_availability_df'], "coach_availability.csv", "phase1")
        config_saver.save_config_to_s3(page_state['baseline_df'], "baseline_data.csv", "phase1")
        ui.notify("Configuration saved successfully!", color="green")
        
    top_bar.top_bar("Phase 1 Configuration")
    
    with ui.row().classes("w-full gap-20"):
        with ui.column().classes("w-1/4 outline outline-cyan-500 outline-offset-10 rounded-lg"):
            with ui.row().classes('w-full items-center gap-3'):
                seed_box = ui.input(label='Seed', value='').props('readonly').classes('w-48')
                generate_seed_button = ui.button(
                    'Generate Seed',
                    on_click=lambda: seed_box.set_value(str(random.randint(0, 999999)))
                )
            with ui.input(label='Phase 1 Start Date (YYYY-MM-DD)').classes('w-full') as start_date_input:
                with ui.menu().props('no-parent-event') as menu:
                    with ui.date().bind_value(start_date_input):
                        with ui.row().classes('justify-end'):
                            ui.button('Select', on_click=menu.close).props('flat')
            with ui.input(label='# of Participants in Individual Condition').classes('w-full') as num_participants_input:
                num_participants_input.props('type=number')
            with ui.input(label='# of Participants in Partner Condition').classes('w-full') as num_participants_partner_input:
                num_participants_partner_input.props('type=number')
                with start_date_input.add_slot('append'):
                    ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
            ui.markdown("**Upload Baseline Data for Participants:**").classes('mt-4')
            ui.upload(label="Upload CSV", on_upload=handle_baselinedata_file_upload).classes('w-full')
            ui.markdown("**Upload Coach Availability Data:**").classes('mt-4')
            ui.upload(label="Upload CSV", on_upload=handle_coach_availability_file_upload).classes('w-full')
            save_config_button = ui.button("Save Configuration", on_click=save_phase1_configuration).classes('w-full mt-4').disable()
    
    if config_saver.check_if_phase_config_exists("phase1", "phase1_configuration.json") and config_saver.check_if_phase_config_exists("phase1", "coach_availability.csv") and config_saver.check_if_phase_config_exists("phase1", "baseline_data.csv"):
        ui.notify("Existing configuration found for Phase 1.", color="blue")
        config_data = config_saver.get_config_from_s3("phase1", "phase1_configuration.json")
        if config_data:
            config = json.loads(config_data)
            seed_box.set_value(config["seed"])
            start_date_input.set_value(config["start_date"])
            num_participants_input.set_value(config["num_participants"])
            num_participants_partner_input.set_value(config["num_participants_partner"])
            generate_seed_button.disable()

    def validate_inputs():
        if seed_box.value and start_date_input.value and num_participants_input.value and num_participants_partner_input.value and page_state['coach_availability_df'] is not None and page_state['baseline_df'] is not None:
            save_config_button.enable()
        else:
            save_config_button.disable()
