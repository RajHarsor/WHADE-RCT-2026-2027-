from nicegui import ui
from ..components import top_bar
from ..functions.participant_display import get_user_info
from ..functions.send_test_sms import send_test_sms

@ui.page('/send_sms')
def send_sms():
    
    def handle_search_for_participant(participant_id, message_type): 
        
        def handle_send_test_sms(phone_number, message):
            
            success, msg = send_test_sms(phone_number, message)
            if success:
                ui.notify(msg, type='positive', close_button=True, timeout=5000)
            else:
                ui.notify(msg, type='negative', close_button=True, timeout=5000)
        
        participant_phone_number_container.clear()
        
        response, msg = get_user_info(participant_id)
        
        if response:
            # Extract phone number
            phone_number = response.get('phone_number')
            ui.notify(f'Found {participant_id}!', type='positive', close_button=True, timeout=5000)
            
            with participant_phone_number_container:
                ui.label(f'Participant Phone Number: {phone_number}').classes('text-lg font-bold')
                
                if message_type == 'Custom Message':
                    message_input = ui.textarea(label='Enter Custom Message').classes('w-100')
                    ui.button('Send Test SMS', on_click=lambda: handle_send_test_sms(phone_number, message_input.value)).props('color=green').classes('w-100')
                elif message_type == 'Hello from the Project WHADE Team! This is a test message.':
                    ui.label('Using Default Message: "Hello from the Project WHADE Team! This is a test message."').classes('text-md italic')
                    message_text = 'Hello from the Project WHADE Team! This is a test message.'
                    ui.button('Send Test SMS', on_click=lambda: handle_send_test_sms(phone_number, message_text)).props('color=green').classes('w-100')
                
        else:
            ui.notify(f'Participant ID {participant_id} not found.', type='negative', close_button=True, timeout=5000)           
            
        
    
    top_bar.top_bar('Send Test SMS')
    
    with ui.row().classes('w-full justify-center gap-15'):
        with ui.column().classes():
            participant_id_input = ui.input(label='Participant ID').classes('w-100')
            message_type = ui.select(label='Message Type', options=['Hello from the Project INSIGHT Team! This is a test message.', 'Custom Message']).classes('w-100')
            ui.button('Search For Participant', on_click=lambda: handle_search_for_participant(participant_id_input.value, message_type.value)).props('color=blue').classes('w-100')
        with ui.column().classes():
            participant_phone_number_container = ui.column().classes('w-100')
            