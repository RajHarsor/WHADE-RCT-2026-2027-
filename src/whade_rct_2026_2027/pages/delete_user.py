from nicegui import ui
from ..components import top_bar
from ..functions.participant_display import delete_user_from_database, get_user_info

@ui.page('/delete_user')
def delete_user():
    
    def handle_view_participant_information_button():
        participant_info_container.clear()
        user_info, message = get_user_info(participant_id_input.value)
        if user_info:
            with participant_info_container:
                ui.markdown('#### Participant Information:')
                ui.markdown(f'- **Participant ID**: {user_info.get("participant_id", "N/A")}')
                ui.markdown(f'- **Week 0 Start Date (Baseline Week)**: {user_info.get("week_0_start_date", "N/A")}')
                ui.markdown(f'- **phase**: {user_info.get("phase", "N/A")}')
                
                ui.button('Delete Participant', on_click=lambda: handle_delete_participant_button(participant_id_input.value)).props('color=red').classes('w-100')
        else:
            ui.notify(message, type='negative', close_button=True, timeout=5000)
                
        def handle_delete_participant_button(participant_id):
            
            def confirm_delete_participant(participant_id, dialog):
                success, message = delete_user_from_database(participant_id)
                if success:
                    ui.notify(f'Participant {participant_id} deleted successfully!', type='positive', close_button=True, timeout=5000)
                    participant_info_container.clear()
                    ui.navigate.to('/')
                else:
                    ui.notify(f'Failed to delete participant {participant_id}: {message}', type='negative', close_button=True, timeout=5000)
                dialog.close()
                
            with ui.dialog() as dialog, ui.card():
                ui.label(f'Are you sure you want to delete participant {participant_id}? This action cannot be undone.')
                with ui.row().classes('justify-center gap-4 w-full'):
                    ui.button('Cancel', on_click=dialog.close).props('flat')
                    ui.button('Delete', on_click=lambda: confirm_delete_participant(participant_id, dialog)).props('color=red')
            
            dialog.open()
            

    
    top_bar.top_bar('Delete Participant')
    
    with ui.row().classes('w-full justify-center gap-20'):
        with ui.column().classes():
            ui.markdown('#### View Participant Information').classes('text-lg font-bold w-100')
            participant_id_input = ui.input(label='Participant ID', validation= {'Must be a number': lambda value: value.isdigit()}).classes('w-100')
            ui.button('Search For Participant', on_click=handle_view_participant_information_button).props('color=blue').classes('w-100')
        with ui.column().classes():
            participant_info_container = ui.column().classes('w-100')