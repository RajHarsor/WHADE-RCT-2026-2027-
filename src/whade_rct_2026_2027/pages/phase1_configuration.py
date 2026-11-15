from datetime import date
from io import BytesIO
import json
import random
from zipfile import ZIP_DEFLATED, ZipFile

import polars as pl
from nicegui import ui

from ..components import top_bar
from ..functions.config_save import ConfigSaver
from ..functions.data_download import DataDownloader
from ..functions.assignments_optimized_final import (
    build_coach_counts,
    get_coach_time_columns,
    main as run_randomization_analysis,
)


config_saver = ConfigSaver()
downloader = DataDownloader()


@ui.page('/phase1')
def phase1_configuration_page():
    page_state = {
        'baseline_df': None,
        'coach_availability_df': None,
        'baseline_uploaded': False,
        'coach_availability_uploaded': False,
    }
    table_individuals_unassigned = None
    table_partners_unassigned = None

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
        has_baseline_csv = page_state['baseline_uploaded'] or (
            config_saver.check_if_phase_config_exists(
                'phase1',
                'baseline_data.csv',
            )
        )
        has_coach_csv = page_state['coach_availability_uploaded'] or (
            config_saver.check_if_phase_config_exists(
                'phase1',
                'coach_availability.csv',
            )
        )
        page_state['baseline_uploaded'] = has_baseline_csv
        page_state['coach_availability_uploaded'] = has_coach_csv

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
            page_state['baseline_uploaded'] = True

            ui.notify(
                f'Baseline CSV uploaded: {event.file.name}',
                color='green',
            )
            validate_inputs()

        except Exception as e:
            page_state['baseline_df'] = None
            page_state['baseline_uploaded'] = False
            ui.notify(f'Error reading baseline CSV: {e}', color='red')
            validate_inputs()

    async def handle_coach_availability_file_upload(event):
        try:
            uploaded_bytes = await event.file.read()
            page_state['coach_availability_df'] = pl.read_csv(
                BytesIO(uploaded_bytes)
            )
            page_state['coach_availability_uploaded'] = True

            ui.notify(
                f'Coach availability CSV uploaded: {event.file.name}',
                color='green',
            )
            validate_inputs()

        except Exception as e:
            page_state['coach_availability_df'] = None
            page_state['coach_availability_uploaded'] = False
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
            config_saver.delete_phase_config(
                'phase1',
                'assignments_randomized_initial.xlsx',
            )
            for filename in (
                'individual_assignments_final.csv',
                'partner_assignments_final.csv',
            ):
                config_saver.delete_phase_config('phase1', filename)
            download_final_randomization_output_button.disable()

            page_state['baseline_uploaded'] = True
            page_state['coach_availability_uploaded'] = True
            ui.notify('Configuration saved successfully!', color='green')
            run_randomization_button.enable()
            save_config_button.disable()
            validate_inputs()

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
            path_to_output, missing_participants = run_randomization_analysis(baseline_df, coach_availability_df, int(seed_box.value))
            # Let the user choose where to save the output file using ui.download
            #ui.notify('Randomization completed successfully!', color='green')
            # save to s3
            config_saver.save_config_to_s3(path_to_output, 'assignments_randomized_initial.xlsx', 'phase1')
            download_randomization_output_button.enable()
            run_randomization_button.disable()
            if missing_participants is None:
                ui.notify(
                    'Randomization output saved to S3, but DynamoDB could not be scanned so the randomization attribute was not updated.',
                    color='orange',
                )
            elif missing_participants:
                ui.notify(
                    f"Randomization output saved to S3. Not in DynamoDB ({len(missing_participants)}): "
                    f"{', '.join(map(str, sorted(missing_participants)))}",
                    color='orange',
                )
            else:
                ui.notify('Randomization output saved to S3 successfully! Please refresh the page to see the updated information.', color='green')
            

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

    def download_final_randomization_output():
        final_output_filenames = (
            'individual_assignments_final.csv',
            'partner_assignments_final.csv',
        )
        downloaded_filenames = []

        try:
            output_files = {}
            for filename in final_output_filenames:
                output_df = downloader.download_csv_from_s3(filename, 'phase1')
                if output_df is not None:
                    output_files[filename] = output_df.write_csv()
                    downloaded_filenames.append(filename)

            if downloaded_filenames:
                coach_availability_df = downloader.download_csv_from_s3(
                    'coach_availability.csv',
                    'phase1',
                )
                if coach_availability_df is not None:
                    coach_counts = build_coach_counts(
                        coach_availability_df,
                        downloader.download_csv_from_s3(
                            'partner_assignments_final.csv',
                            'phase1',
                        ),
                        downloader.download_csv_from_s3(
                            'individual_assignments_final.csv',
                            'phase1',
                        ),
                    )
                    output_files['coach_counts.csv'] = coach_counts.write_csv()

                zip_buffer = BytesIO()
                with ZipFile(zip_buffer, 'w', ZIP_DEFLATED) as archive:
                    for filename, content in output_files.items():
                        archive.writestr(filename, content)
                ui.download(
                    zip_buffer.getvalue(),
                    filename='final_randomization_outputs.zip',
                )
                ui.notify(
                    'Final randomization outputs downloaded successfully!',
                    color='green',
                )
            else:
                download_final_randomization_output_button.disable()
                ui.notify(
                    'No final randomization output found in S3.',
                    color='red',
                )
        except Exception as e:
            ui.notify(
                f'Error downloading final randomization output: {e}',
                color='red',
            )
    
    def delete_phase1_config_popup():
        def delete_phase1_configuration():
            for filename in (
                'assignments_randomized_initial.xlsx',
                'phase1_configuration.json',
                'coach_availability.csv',
                'baseline_data.csv',
                'individual_assignments_final.csv',
                'partner_assignments_final.csv',
            ):
                config_saver.delete_phase_config('phase1', filename)
            dialog.close()
            ui.notify('Phase 1 configuration deleted successfully.', color='green')
            ui.navigate.to('/phase1')

        with ui.dialog() as dialog, ui.card():
            ui.label('Are you sure you want to delete the current Phase 1 configuration? This action cannot be undone.').classes('text-red-600 font-bold w-full justify-center items-center text-center')
            with ui.row().classes('w-full justify-center gap-2'):
                ui.button('Cancel', on_click=dialog.close)
                ui.button(
                    'Delete',
                    color='red',
                    on_click=delete_phase1_configuration,
                )

        dialog.open()

    def _handle_unique_values_for_tables():
        coach_availability_df = downloader.download_csv_from_s3('coach_availability.csv', 'phase1')
        coach_names = coach_availability_df['Initials'].unique().to_list()
        possible_availability_slots = get_coach_time_columns(coach_availability_df)

        randomization_data_bytes = downloader.get_xlsx_from_s3('assignments_randomized_initial.xlsx', 'phase1')
        if randomization_data_bytes:
            sheets = pl.read_excel(BytesIO(randomization_data_bytes), sheet_id=0)
            df_individuals_assigned = sheets['Individual Assignments']
            df_individuals_unassigned = sheets.get('Unassigned Individuals')
            df_partners_assigned = sheets['Partner Assignments']
            df_partners_unassigned = sheets.get('Unassigned Pairs')

            # Combine IDs from assigned and unassigned rows so reassignment can use
            # every participant as a dropdown option.
            individual_id_columns = [df_individuals_assigned['individual_id']]
            if df_individuals_unassigned is not None:
                individual_id_columns.append(df_individuals_unassigned['individual_id'])
            all_individual_ids = pl.concat(individual_id_columns).unique().to_list()

            partner_id_columns = [
                df_partners_assigned.select('partner_1').to_series(),
                df_partners_assigned.select('partner_2').to_series(),
            ]
            if df_partners_unassigned is not None:
                partner_id_columns.extend([
                    df_partners_unassigned.select('partner_1').to_series(),
                    df_partners_unassigned.select('partner_2').to_series(),
                ])
            all_partner_ids = pl.concat(partner_id_columns).unique().to_list()

            GRID_SELECT_OPTIONS = {
                'assigned_coach': coach_names,
                'time_slot': possible_availability_slots,
                'individual_id': all_individual_ids,
                'partner_1': all_partner_ids,
                'partner_2': all_partner_ids,
            }
            return GRID_SELECT_OPTIONS

    def editable_dropdown_grid(df, select_options):
        column_defs = [
            {
                'field': column,
                'editable': column in select_options,
                **(
                    {
                        'cellEditor': 'agSelectCellEditor',
                        'cellEditorParams': {
                            'values': select_options[column],
                        },
                    }
                    if column in select_options
                    else {}
                ),
            }
            for column in df.columns
        ]
        return ui.aggrid.from_polars(
            df,
            options={'columnDefs': column_defs},
        ).classes('w-full')

    def add_manual_assignment_columns(df):
        columns_to_add = [
            pl.lit(None, dtype=pl.String).alias('assigned_coach'),
            pl.lit(None, dtype=pl.String).alias('time_slot'),
        ]
        return df.with_columns(
            column
            for column in columns_to_add
            if column.meta.output_name() not in df.columns
        )

    def load_final_assignment_csv(filenames, rename_mapping):
        for filename in filenames:
            df = downloader.download_csv_from_s3(filename, 'phase1')
            if df is not None:
                return df.rename(rename_mapping)
        return None

    async def save_individual_assignments():
        try:
            individual_rows = await table_individuals_assigned.get_client_data()
            if not individual_assignments_final_loaded and table_individuals_unassigned is not None:
                individual_rows += await table_individuals_unassigned.get_client_data()
            individual_assignments = (
                pl.DataFrame(individual_rows)
                .select(
                    pl.col('individual_id').alias('ID'),
                    pl.col('time_slot'),
                    pl.col('assigned_coach').alias('coach'),
                )
            )
            config_saver.save_config_to_s3(
                individual_assignments,
                'individual_assignments_final.csv',
                'phase1',
            )
            download_final_randomization_output_button.enable()
            ui.notify('Individual assignments saved to S3.', color='green')
        except Exception as e:
            ui.notify(f'Error saving individual assignments: {e}', color='red')

    async def save_partner_assignments():
        try:
            partner_rows = await table_partners_assigned.get_client_data()
            if not partner_assignments_final_loaded and table_partners_unassigned is not None:
                partner_rows += await table_partners_unassigned.get_client_data()
            partner_assignments = pl.DataFrame(partner_rows).select(
                'partner_1',
                'partner_2',
                'time_slot',
                pl.col('assigned_coach').alias('coach'),
            )
            config_saver.save_config_to_s3(
                partner_assignments,
                'partner_assignments_final.csv',
                'phase1',
            )
            download_final_randomization_output_button.enable()
            ui.notify('Partner assignments saved to S3.', color='green')
        except Exception as e:
            ui.notify(f'Error saving partner assignments: {e}', color='red')

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
                'Download Raw Randomization Output',
                on_click=lambda: download_randomization_output(),
            ).classes('w-full mt-1')
            
            download_randomization_output_button.disable()
            
            download_final_randomization_output_button = ui.button(
                'Download Final Randomization Output',
                on_click=download_final_randomization_output,
            ).classes('w-full mt-1')
            
            download_final_randomization_output_button.disable()
            
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

        # Load existing saved configuration and uploads from S3.
        config_file_exists = config_saver.check_if_phase_config_exists(
            'phase1',
            'phase1_configuration.json',
        )
        coach_file_exists = config_saver.check_if_phase_config_exists(
            'phase1',
            'coach_availability.csv',
        )
        baseline_file_exists = config_saver.check_if_phase_config_exists(
            'phase1',
            'baseline_data.csv',
        )
        config_exists = (
            config_file_exists
            and coach_file_exists
            and baseline_file_exists
        )
        page_state['baseline_uploaded'] = baseline_file_exists
        page_state['coach_availability_uploaded'] = coach_file_exists

        if config_exists:
            ui.notify('Existing configuration found for Phase 1.', color='blue')

            page_state['baseline_df'] = downloader.download_csv_from_s3(
                'baseline_data.csv',
                'phase1',
            )
            page_state['coach_availability_df'] = downloader.download_csv_from_s3(
                'coach_availability.csv',
                'phase1',
            )
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
                #run_randomization_button.enable()
                delete_current_config_button.enable()
        
        randomization_output_exists = config_saver.check_if_phase_config_exists(
            'phase1',
            'assignments_randomized_initial.xlsx',
        )
        final_output_exists = any(
            config_saver.check_if_phase_config_exists('phase1', filename)
            for filename in (
                'individual_assignments_final.csv',
                'partner_assignments_final.csv',
            )
        )
        if final_output_exists:
            download_final_randomization_output_button.enable()
        else:
            download_final_randomization_output_button.disable()

        if randomization_output_exists:
            ui.notify('Randomization output found for Phase 1.', color='blue')
            download_randomization_output_button.enable()
            run_randomization_button.disable()
        else:
            ui.notify('No randomization output found for Phase 1.', color='red')
            download_randomization_output_button.disable()
            if config_exists:
                run_randomization_button.enable()
            else:
                run_randomization_button.disable()

        # The button remains disabled until both CSVs are uploaded in this session.
        validate_inputs()
    
        with ui.column().classes('w-2/3 outline outline-cyan-500 outline-offset-10 rounded-lg'):
            with ui.tabs().classes('w-full') as tabs:
                randomization_configuration_final = ui.tab('Configuration Editor').classes('w-full')
                rerandomization_module = ui.tab('Rerandomization Module').classes('w-full')
            with ui.tab_panels(tabs, value=randomization_configuration_final).classes('w-full'):
                if not randomization_output_exists:
                    with ui.tab_panel(randomization_configuration_final).classes('w-full'):
                        ui.label('A valid configuration must be saved before accessing the Configuration Editor.').classes('text-red-600 font-bold w-full justify-center items-center text-center')
                    
                    with ui.tab_panel(rerandomization_module).classes('w-full'):
                        ui.label('A valid configuration must be saved before accessing the Rerandomization Module.').classes('text-red-600 font-bold w-full justify-center items-center text-center')
                else:
                    # get the data
                    randomization_data_bytes = downloader.get_xlsx_from_s3('assignments_randomized_initial.xlsx', 'phase1')
                    if randomization_data_bytes:
                        sheets = pl.read_excel(BytesIO(randomization_data_bytes), sheet_id=0)
                        for name, df in sheets.items():
                            print(f"Sheet: {name}, Rows: {df.shape[0]}, Columns: {df.shape[1]}")
                        grid_select_options = _handle_unique_values_for_tables()
                    df_individuals_assigned = load_final_assignment_csv(
                        ('individual_assignments_final.csv', 'individual_assignments.csv'),
                        {'ID': 'individual_id', 'coach': 'assigned_coach'},
                    )
                    df_partners_assigned = load_final_assignment_csv(
                        ('partner_assignments_final.csv', 'partner_assignments.csv'),
                        {'coach': 'assigned_coach'},
                    )
                    individual_assignments_final_loaded = df_individuals_assigned is not None
                    partner_assignments_final_loaded = df_partners_assigned is not None
                    

                    # randomization configuration editor
                    with ui.tab_panel(randomization_configuration_final).classes('w-full'):
                        with ui.tabs().classes('w-full') as config_tabs:
                            individual_assignments_tab = ui.tab('Individual Assignments').classes('w-full')
                            partner_assignments_tab = ui.tab('Partner Assignments').classes('w-full')
                        with ui.tab_panels(config_tabs, value=individual_assignments_tab).classes('w-full'):
                            with ui.tab_panel(individual_assignments_tab).classes('w-full'):
                                label = ui.label('Assigned Individuals').classes('text-blue-600 font-bold w-full justify-center items-center text-center')
                                if df_individuals_assigned is None:
                                    df_individuals_assigned = sheets['Individual Assignments']
                                table_individuals_assigned = editable_dropdown_grid(df_individuals_assigned, grid_select_options)
                                if not individual_assignments_final_loaded and 'Unassigned Individuals' in sheets:
                                    ui.label(text='Unassigned Individuals').classes('text-blue-600 font-bold w-full justify-center items-center text-center')
                                    df_individuals_unassigned = sheets['Unassigned Individuals']
                                    df_individuals_unassigned = add_manual_assignment_columns(df_individuals_unassigned)
                                    table_individuals_unassigned = editable_dropdown_grid(df_individuals_unassigned, grid_select_options)
                                save_individual_randomization = ui.button(
                                    'Save Final Individual Randomization Output',
                                    on_click=save_individual_assignments,
                                ).classes('justify-center items-center w-full mt-4')
                            with ui.tab_panel(partner_assignments_tab).classes('w-full'):
                                label = ui.label('Assigned Partners').classes('text-blue-600 font-bold w-full justify-center items-center text-center')
                                if df_partners_assigned is None:
                                    df_partners_assigned = sheets['Partner Assignments']
                                table_partners_assigned = editable_dropdown_grid(df_partners_assigned, grid_select_options)
                                if not partner_assignments_final_loaded and 'Unassigned Pairs' in sheets:
                                    ui.label(text='Unassigned Partners').classes('text-blue-600 font-bold w-full justify-center items-center text-center')
                                    df_partners_unassigned = sheets['Unassigned Pairs']
                                    df_partners_unassigned = add_manual_assignment_columns(df_partners_unassigned)
                                    table_partners_unassigned = editable_dropdown_grid(df_partners_unassigned, grid_select_options)
                                save_partner_randomization = ui.button(
                                    'Save Final Partner Randomization Output',
                                    on_click=save_partner_assignments,
                                ).classes('justify-center items-center w-full mt-4')
