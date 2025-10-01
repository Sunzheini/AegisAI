from nicegui import ui

from support.reset_css_for_nicegui import reset_css


class MainApp:
    def __init__(self):
        self.create_app()

    def create_app(self):
        # Complete CSS Reset
        ui.add_head_html(reset_css)

        # Now build your UI with complete control
        with ui.column().classes('w-screen h-screen items-center bg-gray-300'):
            ui.label('1. Api Gateway Service').classes('w-full p-4 text-center text-2xl font-bold')

            with ui.column().classes(
                    'p-4 gap-4 bg-gray-500 border-2 border-gray-300 rounded-lg shadow-lg'):
                self.button1 = ui.button('button 1', on_click=lambda: self.click(1)).classes(
                    'w-1/2 h-12 bg-blue-500 text-white rounded-lg shadow-md')
                self.button2 = ui.button('button 2', on_click=lambda: self.click(2)).classes(
                    'w-1/2 h-12 bg-blue-500 text-white rounded-lg shadow-md')
                self.button3 = ui.button('button 3', on_click=lambda: self.click(3)).classes(
                    'w-1/2 h-12 bg-blue-500 text-white rounded-lg shadow-md')
                self.textarea1 = ui.textarea(label="Multi-line")

    def click(self, nr):
        self.textarea1.set_value(f'button {nr} pressed')


if __name__ in {"__main__", "__mp_main__"}:
    dashboard = MainApp()
    ui.run(title="AegisAI", port=8080, reload=True)
