from nicegui import ui
from ..components import top_bar

@ui.page('/phase1')
def phase1_configuration_page():
    
    top_bar.top_bar("Phase 1 Configuration")
    
    with ui.row().classes("w-full gap-20"):
        with ui.column().classes("w-1/4 justify-left items-left outline outline-cyan-500 outline-offset-10 rounded-lg"):
            with ui.row().classes('w-full justify-center items-center gap-4'):
                seed_label = ui.label('Seed: ')
                generate_seed_button = ui.button('Generate Seed', on_click=lambda: seed_label.set_text(f'Seed: {random.randint(0, 999999)}')).classes('ml-2')