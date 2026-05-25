from nicegui import ui
from sympy import re

from ..components import top_bar
from ..functions.fitbit_functions import *


@ui.page("/single_user_data")
def single_user_data_page():

    def download_csv(dataframe, filename):
        ui.download(dataframe.write_csv().encode("utf-8"), filename=filename)

    def view_single_user_data(participant_id, start_date, end_date):
        auth = FitbitAuth()
        creds = auth.get_credentials(int(participant_id))
        if creds is None:
            ui.notify("No credentials found for this participant ID", color="red")
            return
        
        try:
            combined_df, steps_df, resting_hr_df, sedentary_df, active_minutes_df = auth.get_all_dfs_and_join(participant_id, creds, start_date, end_date)
            exercise_df, exercise_data = auth.get_exercise_data(participant_id, creds, start_date, end_date)
        except Exception as e:
            ui.notify(f"Error fetching data: {str(e)}", color="red")
            return
        
        data_display_container.clear()
        
        with data_display_container.classes("w-5/8 justify-center items-center outline outline-cyan-500 outline-offset-10 rounded-lg"):
            with ui.tabs().classes() as tabs:
                combined_data = ui.tab("Steps, Resting HR, Sedentary Time, Active Minutes")
                activity_data = ui.tab("Activity Data")
            with ui.tab_panels(tabs).classes("w-full justify-center items-center"):
                with ui.tab_panel(combined_data):
                    ui.table.from_polars(combined_df, pagination={'rowsPerPage': 10})
                    with ui.row().classes("w-full justify-center mt-2"):
                        ui.button(
                            "Download CSV",
                            on_click=lambda: download_csv(
                                combined_df,
                                f"participant_{participant_id}_data.csv",
                            ),
                        ).classes("w-1/3")
                with ui.tab_panel(activity_data).classes("w-full justify-center items-center"):
                    ui.table.from_polars(exercise_df, pagination={'rowsPerPage': 10})
                    with ui.row().classes("w-full justify-center mt-2"):
                        ui.button(
                            "Download CSV",
                            on_click=lambda: download_csv(
                                exercise_df,
                                f"participant_{participant_id}_exercise.csv",
                            ),
                        ).classes("w-1/3")


    top_bar.top_bar("Download/View Single Participant Data")

    with ui.row().classes("w-full gap-20"):
        with ui.column().classes(
            "w-1/4 justify-left items-left outline outline-cyan-500 outline-offset-10 rounded-lg"
        ):
            participant_id = (
                ui.input(
                    label="Participant ID",
                    validation={"Must be an integer": lambda x: x.isdigit()},
                )
                .classes("w-full")
                .props("clearable")
            )
            with (
                ui.input(
                    label="Start Date (YYYY-MM-DD)",
                    validation={
                        "Must be a valid date (YYYY-MM-DD)": lambda x: bool(
                            re.match(r"^\d{4}-\d{2}-\d{2}$", x)
                        )
                    },
                )
                .props("clearable")
                .classes("w-full") as start_date_input
            ):
                with ui.menu().props("no-parent-event") as menu:
                    with ui.date().bind_value(start_date_input):
                        with ui.row().classes("justify-end"):
                            ui.button("Select", on_click=menu.close).props("flat")
                with start_date_input.add_slot("append"):
                    ui.icon("edit_calendar").on("click", menu.open).classes(
                        "cursor-pointer"
                    )
            with (
                ui.input(
                    label="End Date (YYYY-MM-DD)",
                    validation={
                        "Must be a valid date (YYYY-MM-DD)": lambda x: bool(
                            re.match(r"^\d{4}-\d{2}-\d{2}$", x)
                        )
                    },
                )
                .props("clearable")
                .classes("w-full") as end_date_input
            ):
                with ui.menu().props("no-parent-event") as menu:
                    with ui.date().bind_value(end_date_input):
                        with ui.row().classes("justify-end"):
                            ui.button("Select", on_click=menu.close).props("flat")
                with end_date_input.add_slot("append"):
                    ui.icon("edit_calendar").on("click", menu.open).classes(
                        "cursor-pointer"
                    )
            ui.button(
                "View Data",
                on_click=lambda: view_single_user_data(
                    participant_id.value,
                    start_date_input.value,
                    end_date_input.value,
                ),
            ).classes("w-full")

        data_display_container = ui.column().classes(
            "w-5/8 justify-right items-right")
