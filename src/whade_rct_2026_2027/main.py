from nicegui import ui
from .pages import home, initialization, add_user

def run() -> None:
    ui.run(title="WHADE RCT 2026-2027", dark=True, reload=True, port=8081)

if __name__ in {"__main__", "__mp_main__"}:
    run()
