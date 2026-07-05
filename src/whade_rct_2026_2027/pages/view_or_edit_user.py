from nicegui import ui
from ..components import top_bar
import re
from ..functions.participant_display import get_user_info, update_user_info

@ui.page('/view_or_edit_user')
def view_or_edit_user_page():

    def handle_view_participant_information_button():
            info_container.clear()
            attribute_edit_container.clear()
            user_info, message = get_user_info(participant_id_input.value)
            #print(user_info, message)
            if user_info:
                # Convert message_randomizer list to string for better display
                if isinstance(user_info.get("message_randomizer"), list):
                    print(user_info["message_randomizer"])
                    print(user_info['message_randomizer'][0])
                    print(user_info['message_randomizer'][1])
                    user_info["message_randomizer"] = ', '.join(map(str, user_info["message_randomizer"]))
                with info_container:
                    ui.markdown('#### Participant Information:')
                    ui.markdown(f'- **Participant ID**: {user_info.get("participant_id", "N/A")}')
                    ui.markdown(f'- **Phase**: {user_info.get("phase", "N/A")}')
                    ui.markdown(f'- **Week 0 Start Date (Baseline Week)**: {user_info.get("week_0_start_date", "N/A")}')

                    
                with attribute_edit_container:
                    
                    def handle_submit_changes(participant_id, attribute, new_value):
                        new_participant_info_container.clear()
                        success, message1 = update_user_info(participant_id, attribute, new_value)
                        if success:
                            ui.notify(f'Updated {attribute} successfully!', type='positive', close_button=True, timeout=5000)
                            user_info, message2 = get_user_info(participant_id)
                            with new_participant_info_container:
                                ui.markdown('#### Updated Participant Information:')
                                ui.markdown(f'- **Participant ID**: {user_info.get("participant_id", "N/A")}')
                                ui.markdown(f'- **Phase**: {user_info.get("phase", "N/A")}')
                                ui.markdown(f'- **Week 0 Start Date (Baseline Week)**: {user_info.get("week_0_start_date", "N/A")}')
                        else:
                            ui.notify(f'Failed to update {attribute}: {message1}', type='negative', close_button=True, timeout=5000)
                            return
                        user_info, message2 = get_user_info(participant_id)


                    def handle_input():
                        new_value_container.clear()
                        with new_value_container:
                            if attribute_select.value == 'Week 0 Start Date (week_0_start_date)':
                                # Strip the attribute name from the select value
                                attribute_name_stripped = attribute_select.value.split('(')[-1].rstrip(')')
                                with ui.input('Insert Date', validation={'Must be a date in the format YYYY-MM-DD': lambda value: bool(re.match(r'^\d{4}-\d{2}-\d{2}$', value))}).classes('w-100') as date_input:
                                    with ui.menu().props('no-parent-event') as menu:
                                        with ui.date().bind_value(date_input):
                                            with ui.row().classes('justify-end'):
                                                ui.button('Close', on_click=menu.close).props('flat')
                                        with date_input.add_slot('append'):
                                            ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
                                ui.button('Submit Changes', on_click= lambda: handle_submit_changes(participant_id_input.value, attribute_name_stripped, date_input.value)).props('color=red').classes('w-100')
                            elif attribute_select.value == 'Phase (phase)':
                                attribute_name_stripped = attribute_select.value.split('(')[-1].rstrip(')')
                                new_value = ui.input(label='Insert New Value').classes('w-100')
                                ui.button('Submit Changes', on_click=lambda: handle_submit_changes(participant_id_input.value, attribute_name_stripped, new_value.value)).props('color=red').classes('w-100')
                
                    ui.markdown('#### Edit Participant Attributes:')
                    attribute_select = ui.select(label='Select Attribute to Edit', options=['Week 0 Start Date (week_0_start_date)', 'Phase (phase)'], on_change=handle_input).classes('w-100')
            else:
                ui.notify(message, type='negative', close_button=True, timeout=5000)
        
    top_bar.top_bar('View/Edit Participant Page')
    
    with ui.row().classes('w-full justify-center gap-20'):
        with ui.column().classes():
            ui.markdown('#### View Participant Information').classes('text-lg font-bold w-100')
            participant_id_input = ui.input(label='Participant ID', validation= {'Must be a number': lambda value: value.isdigit()}).classes('w-100')
            ui.button('View Participant Information', on_click=handle_view_participant_information_button).props('color=blue').classes('w-100')

            info_container = ui.column().classes('mt-5 w-100')
        with ui.column().classes():
            attribute_edit_container = ui.column().classes('w-100')
            new_value_container = ui.column().classes('w-100')
            new_participant_info_container = ui.column().classes('w-100')
    