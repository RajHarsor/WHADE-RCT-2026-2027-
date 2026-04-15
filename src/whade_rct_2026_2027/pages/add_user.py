from nicegui import ui
from ..components import top_bar
import re

@ui.page('/add_user')
def add_user_page():
    top_bar.top_bar("Add Participant (Fitbit)")
    
    with ui.row().classes('justify-center w-full'):
        with ui.column().classes('w-1/3'):
            participant_id = ui.input(label="Participant ID", validation={'Must be an integer': lambda x: x.isdigit()}).props('clearable')
            with ui.input(label="Week 0 Start Date", validation={'Must be a valid date (YYYY-MM-DD)': lambda x: bool(re.match(r'^\d{4}-\d{2}-\d{2}$', x))}).props('clearable') as date_input:
                with ui.menu().props('no-parent-event') as menu:
                    with ui.date().bind_value(date_input):
                        with ui.row().classes('justify-end'):
                            ui.button("Select", on_click=menu.close).props('flat')
            ui.button("Generate Authorization URL").classes('w-full')
        
        with ui.column().classes('w-1/3'):