from datetime import date
from io import BytesIO
import json
import random

import polars as pl
from nicegui import ui

from ..components import top_bar
from ..functions.config_save import ConfigSaver
from ..functions.data_download import DataDownloader
from ..functions.assignments_optimized_final import main as run_randomization_analysis


config_saver = ConfigSaver()
downloader = DataDownloader()


@ui.page('/phase1')
def phase1_configuration_page():
    page_state = {
        'baseline_df': None,
        'coach_availability_df': None,
    }

    def validate_baseline_csv(df):
        # load the csv to check the number of rows and check that it equals individual participants + partner participants
        num_rows = df.shape[0]
        num_individual_participants = int(num_participants_input.value)
        num_partner_participants = int(num_participants_partner_input.value)
        expected_rows = num_individual_participants + num_partner_participants
        if num_rows != expected_rows:
            ui.notify(
                f'Baseline CSV has {num_rows} rows, but expected {expected_rows} rows based on participant counts.',
                color='red',
            )
            return False
        return True
        
    def validate_inputs():
        """Enable Save only when all fields and both CSV files are present."""
        has_seed = seed_box.value not in (None, '')
        has_start_date = start_date_input.value not in (None, '')
        has_individual_count = num_participants_input.value not in (None, '')
        has_partner_count = num_participants_partner_input.value not in (None, '')
        has_baseline_csv = page_state['baseline_df'] is not None
        has_coach_csv = page_state['coach_availability_df'] is not None

        is_valid = (
            has_seed
            and has_start_date
            and has_individual_count
            and has_partner_count
            and has_baseline_csv
            and has_coach_csv
        )

        if is_valid:
            validate_baseline_csv(page_state['baseline_df'])
            if validate_baseline_csv(page_state['baseline_df']) == True:
                ui.notify('Baseline CSV validation passed.', color='green')
                save_config_button.enable()
            else:
                save_config_button.disable()
                ui.notify('Baseline CSV validation failed. Please check the number of rows.', color='red')
                is_valid = False

        print(
            f'Valid: {is_valid} | '
            f'Seed: {seed_box.value!r} | '
            f'Start Date: {start_date_input.value!r} | '
            f'Individual Participants: {num_participants_input.value!r} | '
            f'Partner Participants: {num_participants_partner_input.value!r} | '
            f'Baseline CSV uploaded: {has_baseline_csv} | '
            f'Coach Availability CSV uploaded: {has_coach_csv}'
        )

    def generate_seed():
        seed_box.set_value(str(random.randint(0, 999999)))
        validate_inputs()

    async def handle_baselinedata_file_upload(event):
        try:
            uploaded_bytes = await event.file.read()
            page_state['baseline_df'] = pl.read_csv(BytesIO(uploaded_bytes))

            ui.notify(
                f'Baseline CSV uploaded: {event.file.name}',
                color='green',
            )
            validate_inputs()

        except Exception as e:
            page_state['baseline_df'] = None
            ui.notify(f'Error reading baseline CSV: {e}', color='red')
            validate_inputs()

    async def handle_coach_availability_file_upload(event):
        try:
            uploaded_bytes = await event.file.read()
            page_state['coach_availability_df'] = pl.read_csv(
                BytesIO(uploaded_bytes)
            )

            ui.notify(
                f'Coach availability CSV uploaded: {event.file.name}',
                color='green',
            )
            validate_inputs()

        except Exception as e:
            page_state['coach_availability_df'] = None
            ui.notify(
                f'Error reading coach availability CSV: {e}',
                color='red',
            )
            validate_inputs()

    def save_phase1_configuration():
        seed = seed_box.value
        start_date = start_date_input.value
        num_participants = num_participants_input.value
        num_participants_partner = num_participants_partner_input.value

        if not all([
            seed,
            start_date,
            num_participants,
            num_participants_partner,
        ]):
            ui.notify('Please fill in all fields.', color='red')
            return

        if (
            page_state['baseline_df'] is None
            or page_state['coach_availability_df'] is None
        ):
            ui.notify('Please upload both CSV files before saving.', color='red')
            return

        config_data = {
            'seed': seed,
            'start_date': start_date,
            'num_participants': num_participants,
            'num_participants_partner': num_participants_partner,
        }

        try:
            config_saver.save_config_to_s3(
                config_data,
                'phase1_configuration.json',
                'phase1',
            )
            config_saver.save_config_to_s3(
                page_state['coach_availability_df'],
                'coach_availability.csv',
                'phase1',
            )
            config_saver.save_config_to_s3(
                page_state['baseline_df'],
                'baseline_data.csv',
                'phase1',
            )

            ui.notify('Configuration saved successfully!', color='green')

        except Exception as e:
            ui.notify(f'Error saving configuration: {e}', color='red')
        
    def run_randomization():
        # get the baseline data and coach availability from s3
        baseline_df = downloader.download_csv_from_s3('baseline_data.csv', 'phase1')
        coach_availability_df = downloader.download_csv_from_s3('coach_availability.csv', 'phase1')
        
        # DEBUG BLOCK
        print("Baseline DataFrame:")
        print(baseline_df)
        print("Coach Availability DataFrame:")
        print(coach_availability_df)
        
        # run randomization
        try:
            path_to_output = run_randomization_analysis(baseline_df, coach_availability_df, int(seed_box.value))
            # Let the user choose where to save the output file using ui.download
            #ui.notify('Randomization completed successfully!', color='green')
            # save to s3
            config_saver.save_config_to_s3(path_to_output, 'assignments_randomized_initial.xlsx', 'phase1')
            ui.notify('Randomization output saved to S3 successfully!', color='green')
            

        except Exception as e:
            ui.notify(f'Error running randomization: {e}', color='red')
        
    def download_randomization_output():
        try:
            # Download the randomization output from S3
            output_bytes = downloader.get_xlsx_from_s3('assignments_randomized_initial.xlsx', 'phase1')
            if output_bytes:
                ui.download(output_bytes, filename='assignments_randomized_initial.xlsx')
                ui.notify('Randomization output downloaded successfully!', color='green')
            else:
                ui.notify('Randomization output not found in S3.', color='red')
        except Exception as e:
            ui.notify(f'Error downloading randomization output: {e}', color='red')
    
    def delete_phase1_config_popup():
        with ui.dialog() as dialog, ui.card():
            ui.label('Are you sure you want to delete the current Phase 1 configuration? This action cannot be undone.').classes('text-red-600 font-bold w-full justify-center items-center text-center')
            with ui.row().classes('w-full justify-center gap-2'):
                ui.button('Cancel', on_click=dialog.close)
                ui.button(
                    'Delete',
                    color='red',
                    on_click=lambda: config_saver.delete_phase_config('phase1', 'assignments_randomized_initial.xlsx') & config_saver.delete_phase_config('phase1', 'phase1_configuration.json') & config_saver.delete_phase_config('phase1', 'coach_availability.csv') & config_saver.delete_phase_config('phase1', 'baseline_data.csv') & dialog.close() & ui.notify('Phase 1 configuration deleted successfully.', color='green')
                )

        dialog.open()

#=================================================================================#
    top_bar.top_bar('Phase 1 Configuration')

    with ui.row().classes('w-full gap-20'):
        with ui.column().classes(
            'w-1/4 outline outline-cyan-500 outline-offset-10 rounded-lg'
        ):
            with ui.row().classes('w-full items-center gap-3'):
                seed_box = (
                    ui.input(label='Seed', value='')
                    .props('readonly')
                    .classes('w-48')
                )

                generate_seed_button = ui.button(
                    'Generate Seed',
                    on_click=generate_seed,
                )

            with (
                ui.input(label='Phase 1 Start Date (YYYY-MM-DD)')
                .classes('w-full')
                as start_date_input
            ):
                with ui.menu().props('no-parent-event') as start_date_menu:
                    with ui.date().bind_value(start_date_input):
                        with ui.row().classes('justify-end'):
                            ui.button(
                                'Select',
                                on_click=start_date_menu.close,
                            ).props('flat')

                with start_date_input.add_slot('append'):
                    ui.icon('edit_calendar').on(
                        'click',
                        start_date_menu.open,
                    ).classes('cursor-pointer')

            num_participants_input = (
                ui.input(label='# of Participants in Individual Condition')
                .props('type=number')
                .classes('w-full')
            )

            num_participants_partner_input = (
                ui.input(label='# of Participants in Partner Condition')
                .props('type=number')
                .classes('w-full')
            )

            ui.markdown('**Upload Baseline Data for Participants:**').classes(
                'mt-4'
            )
            ui.upload(
                label='Upload CSV',
                on_upload=handle_baselinedata_file_upload,
            ).classes('w-full')

            ui.markdown('**Upload Coach Availability Data:**').classes(
                'mt-4'
            )
            ui.upload(
                label='Upload CSV',
                on_upload=handle_coach_availability_file_upload,
            ).classes('w-full')

            save_config_button = ui.button(
                'Save Configuration',
                on_click=save_phase1_configuration,
            ).classes('w-full mt-4')

            save_config_button.disable()

            run_randomization_button = ui.button(
                'Run Randomization',
                on_click=run_randomization,
                ).classes('w-full mt-1')
            
            run_randomization_button.disable()
            
            download_randomization_output_button = ui.button(
                'Download Randomization Output',
                on_click=lambda: download_randomization_output(),
            ).classes('w-full mt-1')
            
            download_randomization_output_button.disable()
            
            delete_current_config_button = ui.button(
                'Delete Current Configuration',
                on_click=lambda: delete_phase1_config_popup(),
                color='red'
            ).classes('w-full mt-1')
            
            delete_current_config_button.disable()
                    
    

        # Run validation whenever a normal form field changes.
        seed_box.on('update:model-value', lambda _: validate_inputs())
        start_date_input.on('update:model-value', lambda _: validate_inputs())
        num_participants_input.on('update:model-value', lambda _: validate_inputs())
        num_participants_partner_input.on(
            'update:model-value',
            lambda _: validate_inputs(),
        )

        # Load existing saved configuration, if all expected S3 files exist.
        config_exists = (
            config_saver.check_if_phase_config_exists(
                'phase1',
                'phase1_configuration.json',
            )
            and config_saver.check_if_phase_config_exists(
                'phase1',
                'coach_availability.csv',
            )
            and config_saver.check_if_phase_config_exists(
                'phase1',
                'baseline_data.csv',
            )
        )

        if config_exists:
            ui.notify('Existing configuration found for Phase 1.', color='blue')

            config_data = config_saver.get_config_from_s3(
                'phase1',
                'phase1_configuration.json',
            )

            if config_data:
                config = json.loads(config_data)

                seed_box.set_value(config['seed']).disable()
                start_date_input.set_value(config['start_date']).disable()
                num_participants_input.set_value(config['num_participants']).disable()
                num_participants_partner_input.set_value(
                    config['num_participants_partner']
                ).disable()

                generate_seed_button.disable()
                save_config_button.disable()
                run_randomization_button.disable()
                delete_current_config_button.enable()
        
        randomization_output_exists = config_saver.check_if_phase_config_exists(
            'phase1',
            'assignments_randomized_initial.xlsx',
        )
        
        if randomization_output_exists:
            ui.notify('Randomization output found for Phase 1.', color='blue')
            download_randomization_output_button.enable()
            run_randomization_button.disable()

        # The button remains disabled until both CSVs are uploaded in this session.
        validate_inputs()
    
        with ui.column().classes('w-2/3 outline outline-cyan-500 outline-offset-10 rounded-lg'):
            with ui.tabs().classes('w-full') as tabs:
                randomization_configuration_final = ui.tab('Randomization Editor').classes('w-full')
                rerandomization_module = ui.tab('Rerandomization Module').classes('w-full')
            with ui.tab_panels(tabs, value=randomization_configuration_final).classes('w-full'):
                if not config_exists:
                    with ui.tab_panel(randomization_configuration_final).classes('w-full'):
                        ui.label('A valid configuration must be saved before accessing the Randomization Editor.').classes('text-red-600 font-bold w-full justify-center items-center text-center')
                    
                    with ui.tab_panel(rerandomization_module).classes('w-full'):
                        ui.label('A valid configuration must be saved before accessing the Rerandomization Module.').classes('text-red-600 font-bold w-full justify-center items-center text-center')