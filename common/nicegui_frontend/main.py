from nicegui import ui

from support.reset_css_for_nicegui import reset_css


class MainApp:
    """
    An example of a complete NiceGUI application with custom CSS reset and structured layout. Used for AegisAI
    microservices showcase.
    """
    def __init__(self):
        # general
        self._title = "AegisAI Microservices Showcase"
        self._spinner = None

        # app1
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

        # Create spinner first (initially hidden)
        self._spinner = ui.spinner(size='lg', color='white').classes('absolute inset-0 m-auto z-50')
        self._spinner.set_visibility(False)

        # UI Layout
        with ui.column().classes('w-screen h-screen bg-gray-300 justify-start gap-0 relative'):
            ui.label(self._title).classes('w-full p-4 text-center text-2xl font-bold border border-white')

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

    # region general methods ------------------------------------------------------------------------------------------
    def _disable_buttons(self, disable: bool):
        """Enable or disable all buttons"""
        for i in range(1, 4):
            button = getattr(self, f'app1_button{i}', None)
            if button:
                if disable:
                    button.props('disable')
                    button.classes('opacity-50 cursor-not-allowed')
                else:
                    button.props(remove='disable')
                    button.classes(remove='opacity-50 cursor-not-allowed')

    # endregion -------------------------------------------------------------------------------------------------------

    # region app1 event handlers --------------------------------------------------------------------------------------
    def click(self, nr):
        self._spinner.set_visibility(True)
        self._disable_buttons(True)

        def finish_operation():
            self._spinner.set_visibility(False)
            self._disable_buttons(False)
            self.app1_textarea1.set_value(f'button {nr} pressed')

        # 2-second non-blocking timer
        ui.timer(2.0, finish_operation, once=True)

    # endregion -------------------------------------------------------------------------------------------------------


if __name__ in {"__main__", "__mp_main__"}:
    dashboard = MainApp()
    ui.run(title="AegisAI", port=8080, reload=True)
