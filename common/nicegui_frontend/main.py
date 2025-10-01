from nicegui import ui

from support.reset_css_for_nicegui import reset_css


class MainApp:
    """
    An example of a complete NiceGUI application with custom CSS reset and structured layout. Used for AegisAI
    microservices showcase.
    """
    def __init__(self):
        # App1
        self._app1_label = None
        self._app1_button1 = None
        self._app1_button2 = None
        self._app1_button3 = None
        self._app1_textarea1 = None

        self.create_app1()

    # region getters and setters for app1 -----------------------------------------------------------------------------
    @property
    def app1_label(self):
        return self._app1_label

    @app1_label.setter
    def app1_label(self, value):
        if self._app1_label is None:
            self._app1_label = value

    @property
    def app1_button1(self):
        return self._app1_button1

    @app1_button1.setter
    def app1_button1(self, value):
        if self._app1_button1 is None:
            self._app1_button1 = value

    @property
    def app1_button2(self):
        return self._app1_button2

    @app1_button2.setter
    def app1_button2(self, value):
        if self._app1_button2 is None:
            self._app1_button2 = value

    @property
    def app1_button3(self):
        return self._app1_button3

    @app1_button3.setter
    def app1_button3(self, value):
        if self._app1_button3 is None:
            self._app1_button3 = value

    @property
    def app1_textarea1(self):
        return self._app1_textarea1

    @app1_textarea1.setter
    def app1_textarea1(self, value):
        if self._app1_textarea1 is None:
            self._app1_textarea1 = value

    # endregion -------------------------------------------------------------------------------------------------------

    # region app1 -----------------------------------------------------------------------------------------------------
    def create_app1(self) -> None:
        """
        Create the NiceGUI application with a complete CSS reset and structured layout.
        This function sets up the main UI components and their styles.
        :return: None
        """
        # Complete CSS Reset
        ui.add_head_html(reset_css)

        # UI Layout
        with ui.column().classes('w-screen h-screen bg-gray-300 justify-start gap-0'):
            ui.label('AegisAI Microservices Showcase').classes('w-full p-4 text-center text-2xl font-bold border border-white')

            with ui.column().classes('w-[calc(100%-2rem)] mx-auto p-4 gap-4 '                       # size
                                     'bg-gray-400 border-2 border-white rounded-lg shadow-lg '      # style
                                     'overflow-auto items-start'):                                  # children
                self.app1_label = ui.label('1. Api Gateway Service').classes('w-1/2 p-4 text-center text-xl font-bold border border-white')

                self.app1_button1 = ui.button('button 1', on_click=lambda: self.click(1)).classes(
                    'w-1/2 h-12 bg-blue-500 text-white rounded-lg shadow-md')

                self.app1_button2 = ui.button('button 2', on_click=lambda: self.click(2)).classes(
                    'w-1/2 h-12 bg-blue-500 text-white rounded-lg shadow-md')

                self.app1_button3 = ui.button('button 3', on_click=lambda: self.click(3)).classes(
                    'w-1/2 h-12 bg-blue-500 text-white rounded-lg shadow-md')

                self.app1_textarea1 = ui.textarea(label="Multi-line").classes('border border-white')

    # endregion -------------------------------------------------------------------------------------------------------

    # region app1 event handlers --------------------------------------------------------------------------------------
    def click(self, nr):
        self.app1_textarea1.set_value(f'button {nr} pressed')

    # endregion -------------------------------------------------------------------------------------------------------


if __name__ in {"__main__", "__mp_main__"}:
    dashboard = MainApp()
    ui.run(title="AegisAI", port=8080, reload=True)
