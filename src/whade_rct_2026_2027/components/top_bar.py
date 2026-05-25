from nicegui import ui

def menu():
    with ui.button(icon='menu'):
        with ui.menu():
            ui.menu_item('Homepage', on_click=lambda: ui.navigate.to('/'))
            ui.menu_item('Initialization', on_click=lambda: ui.navigate.to('/initialization'))
            ui.menu_item('Add Participant (Fitbit)', on_click=lambda: ui.navigate.to('/add_user'))
            with ui.menu_item('View/Edit Participant', auto_close=False):
                with ui.item_section().props('side'):
                    ui.icon('keyboard_arrow_right')
                with ui.menu().props('anchor="top end" self="top start" auto-close'):
                    ui.menu_item("View/Edit Participant Details", on_click=lambda: ui.navigate.to('/view_edit_user'))
                    ui.menu_item("Delete Participant", on_click=lambda: ui.navigate.to('/delete_user'))
            #ui.menu_item('Send Test SMS', on_click=lambda: ui.navigate.to('/send_sms'))
            with ui.menu_item('Participant Checks', auto_close=False):
                with ui.item_section().props('side'):
                    ui.icon('keyboard_arrow_right')
                with ui.menu().props('anchor="top end" self="top start" auto-close'):
                    ui.menu_item("Download/View Single Participant Data", on_click=lambda: ui.navigate.to('/single_user_data'))
                    ui.menu_item("Download Aggregate Data", on_click=lambda: ui.navigate.to('/individual_compliance_check'))
            

def top_bar(page_title: str):
    dark = ui.dark_mode(True)
    
    if not getattr(top_bar, "_reset_done", False):
        ui.add_head_html("""<style>html, body { margin: 0; padding: 0; }</style>""")
        top_bar._reset_done = True
    
    with ui.row().classes('w-screen items-center no-wrap justify-between mb-3 bg-blue-500 mt-0').style('position: fixed; top: 0; left: 0; right: 0; z-index: 1000;'):
        
        with ui.row().classes('justify-start'):
            menu()
            ui.button(icon='home', on_click=lambda: ui.navigate.to('/')).props('flat color=white')
            
            
        with ui.row().classes('justify-center'):
            ui.label(page_title).classes('text-h5')  
                
        with ui.row().classes('justify-end'):
            ui.switch('Dark Mode').bind_value(dark).classes('pr-3')
    
    ui.html('<div style="height:56px"></div>', sanitize=False) 