from nicegui import ui
from ..components import top_bar
from ..functions.fitbit_functions import *
import re
import asyncio
from datetime import date

@ui.page('/add_user')
def add_user_page():
    top_bar.top_bar("Add Participant (Fitbit)")

    with ui.column().classes('w-full justify-center items-center'):
        participant_id = ui.input(label="Participant ID", validation={'Must be an integer': lambda x: x.isdigit()}).classes('w-full').props('clearable')
        phase = ui.select(label="Phase", options=["Phase 1", "Phase 2", "Phase 3"]).classes('w-full').props('clearable')
        with ui.input(label="Week 0 Start Date", validation={'Must be a valid date (YYYY-MM-DD)': lambda x: bool(re.match(r'^\d{4}-\d{2}-\d{2}$', x))}).props('clearable').classes('w-full') as date_input:
            with ui.menu().props('no-parent-event') as menu:
                with ui.date().bind_value(date_input):
                    with ui.row().classes('justify-end'):
                        ui.button("Select", on_click=menu.close).props('flat')
            with date_input.add_slot('append'):
                ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
        ui.button("Generate Authorization URL").classes('w-full').on_click(lambda: generate_authorization_url(participant_id, phase, date_input))

def generate_authorization_url(participant_id, phase, week_0_start_date):
    auth = FitbitAuth()
    auth_url, flow = auth.generate_auth_link()
    
    def test_steps_pulling(participant_id):
        try:
            creds = auth.get_credentials(int(participant_id))
            if creds is None:
                ui.notify("No saved tokens found for this participant.", color="red")
                return

            todays_date = date.today().strftime("%Y-%m-%d")
            steps = auth.aggregate_steps_over_time(int(participant_id), creds, todays_date, todays_date)
            steps_total = steps["steps"][0] if len(steps) else 0
            ui.notify(f"Steps pulled for today: {steps_total}", color="green")
        except Exception as e:
            ui.notify(f"Error pulling steps: {e}", color="red")

    async def submit_button():
        phase_mapping = {"Phase 1": 1, "Phase 2": 2, "Phase 3": 3}
        phase_value = phase_mapping.get(phase.value)
        result = auth.save_tokens(int(participant_id.value), phase_value, week_0_start_date.value, url_input.value, flow)
        if result is None:
            ui.notify("Tokens saved successfully!", color="green")
            pull_steps_button.enable()
            submit_tokens_button.disable()
            await asyncio.sleep(2)
            #ui.navigate.to('/')
        else:
            ui.notify(f"Error saving tokens. Error: {result}", color="red")

    with ui.dialog() as dialog, ui.card():
        ui.label("Fitbit Authorization Steps").classes('text-h6')
        ui.markdown(f"1. Send the participant the following URL and ask them to open it in their browser").classes('whitespace-normal break-all')
        with ui.row().classes('w-full justify-center'):
            ui.button("Copy URL to Clipboard", on_click=lambda: ui.clipboard.write(auth_url))
        ui.markdown("2. The participant will be prompted to login or choose an account. Given that this is now the Google Health API, a Google account will be required.")
        ui.markdown("3. After selecting an account, they will be directed to a page with a hazard screen. Have the participant click 'Advanced' and then click 'Go to wordpress.com (unsafe)'.")
        ui.markdown("4. Participants will be redirected to a page on the CHASE Lab website. Have them copy the entire URL from the address bar and send it back to you.")
        ui.markdown("5. Paste the URL into the input below and click 'Submit'.")
        url_input = ui.input(label="Redirected URL").classes('w-full')
        with ui.row().classes('w-full justify-center'):
            submit_tokens_button = ui.button("Submit", on_click=submit_button).classes('w-1/4')
            pull_steps_button = ui.button("Pull Todays Steps", on_click=lambda: test_steps_pulling(participant_id.value)).classes('w-1/4')
            pull_steps_button.disable()
            ui.button("Go Home", on_click=lambda: ui.navigate.to('/')).classes('w-1/4')

        dialog.open()