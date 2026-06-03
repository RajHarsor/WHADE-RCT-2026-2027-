from nicegui import ui
from ..components import top_bar
import asyncio

@ui.page('/')
def home_page():
    top_bar.top_bar("WHADE RCT Management Dashboard")
    
    with ui.row().classes('justify-center w-full'):
        # Phase 1
        with ui.card().classes('w-1/4'):
            with ui.row().classes('w-full justify-center items-center gap-4'):
                phase1_light = ui.icon('fiber_manual_record', size='3em').classes('text-red')
                ui.label("Phase 1").classes('text-h6')
            ui.button("Configure", on_click=lambda: ui.navigate.to('/phase1')).classes('w-full')
        ui.icon('arrow_forward').classes('text-6xl self-center')
        # Phase 2
        with ui.card().classes('w-1/4'):
            with ui.row().classes('w-full justify-center items-center gap-4'):
                phase2_light = ui.icon('fiber_manual_record', size='3em').classes('text-red')
                ui.label("Phase 2").classes('text-h6')
            ui.button("Configure", on_click=lambda: ui.navigate.to('/phase2')).classes('w-full')
        ui.icon('arrow_forward').classes('text-6xl self-center')
        # Phase 3
        with ui.card().classes('w-1/4'):
            with ui.row().classes('w-full justify-center items-center gap-4'):
                phase3_light = ui.icon('fiber_manual_record', size='3em').classes('text-red')
                ui.label("Phase 3").classes('text-h6')
            ui.button("Configure", on_click=lambda: ui.navigate.to('/phase3')).classes('w-full')
    
    ui.timer(0, lambda: asyncio.create_task(blinking_indicator([phase1_light, phase2_light, phase3_light])), once=True)

async def blinking_indicator(indicators):
    while True:
        for indicator in indicators:
            indicator.classes('text-transparent', remove='text-red')
        await asyncio.sleep(1)
        
        for indicator in indicators:
            indicator.classes('text-red', remove='text-transparent')
        await asyncio.sleep(1)