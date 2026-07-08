# to run for testing: python -m whade_rct_2026_2027.main

from nicegui import ui
from .pages import home, initialization, add_user, download_view_single_user_data, phase1_configuration, download_view_aggregated_data, view_or_edit_user, delete_user

def run() -> None:
    ui.run(title="WHADE RCT 2026-2027", dark=True, reload=True, port=8085)

if __name__ in {"__main__", "__mp_main__"}:
    run(refresh=False)
