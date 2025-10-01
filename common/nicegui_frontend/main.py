import asyncio
import json
import aiohttp          # async HTTP client instead of requests!
from nicegui import ui
from support.reset_css_for_nicegui import reset_css


class MainApp:
    def __init__(self):
        # general
        self._title = "AegisAI Microservices Showcase"
        self._spinner = None
        self._access_token = None

        # service1
        self._service1_label = None
        self._service1_button1 = None
        self._service1_button2 = None
        self._service1_button3 = None
        self._service1_textarea1 = None

        self.create_app()

    # region general methods ------------------------------------------------------------------------------------------
    def _disable_buttons(self, disable: bool):
        """Enable or disable all buttons"""
        for i in range(1, 4):
            button = getattr(self, f'_service1_button{i}', None)
            if button:
                if disable:
                    button.props('disable')
                    button.classes('opacity-50 cursor-not-allowed')
                else:
                    button.props(remove='disable')
                    button.classes(remove='opacity-50 cursor-not-allowed')

    async def _base_request_handler(self, method_type: str, url: str, data=None, headers=None):
        """Async base handler for requests"""
        self._spinner.set_visibility(True)
        self._disable_buttons(True)

        try:
            async with aiohttp.ClientSession() as session:
                if method_type == 'get':
                    async with session.get(url, headers=headers) as response:
                        result_text = await response.text()
                        self._service1_textarea1.set_value(
                            f"Status: {response.status}\n{result_text}")  # ← response.status

                        if response.status == 200:
                            try:
                                response_data = await response.json()
                                if url.endswith('/auth/login') and 'access_token' in response_data:
                                    self._access_token = response_data['access_token']
                                    ui.notify("Login successful! Token stored.")
                            except:
                                # If response is not JSON, just show the text
                                pass

                elif method_type == 'post':
                    if url.endswith('/auth/login') and data:
                        # Form data for login
                        async with session.post(url, data=data) as response:
                            result_text = await response.text()
                            self._service1_textarea1.set_value(
                                f"Status: {response.status}\n{result_text}")  # ← response.status

                            if response.status == 200:
                                try:
                                    response_data = await response.json()
                                    if 'access_token' in response_data:
                                        self._access_token = response_data['access_token']
                                        ui.notify("Login successful! Token stored.")
                                except:
                                    pass
                    else:
                        # JSON data for other endpoints
                        async with session.post(url, json=data, headers=headers) as response:
                            result_text = await response.text()
                            self._service1_textarea1.set_value(
                                f"Status: {response.status}\n{result_text}")  # ← response.status

                            if response.status == 200:
                                try:
                                    response_data = await response.json()
                                    self._service1_textarea1.set_value(json.dumps(response_data, indent=4))
                                except:
                                    # If response is not JSON, keep the text response
                                    pass

                else:
                    ui.notify(f"Unsupported method type: {method_type}")

        except Exception as e:
            ui.notify(f"Error during execution: {str(e)}")
            self._service1_textarea1.set_value(f"Error: {str(e)}")
        finally:
            self._spinner.set_visibility(False)
            self._disable_buttons(False)

    # endregion -------------------------------------------------------------------------------------------------------

    # region getters and setters for service1 -------------------------------------------------------------------------
    @property
    def service1_label(self):
        return self._service1_label

    @service1_label.setter
    def service1_label(self, value):
        if self._service1_label is None:
            self._service1_label = value

    @property
    def service1_button1(self):
        return self._service1_button1

    @service1_button1.setter
    def service1_button1(self, value):
        if self._service1_button1 is None:
            self._service1_button1 = value

    @property
    def service1_button2(self):
        return self._service1_button2

    @service1_button2.setter
    def service1_button2(self, value):
        if self._service1_button2 is None:
            self._service1_button2 = value

    @property
    def service1_button3(self):
        return self._service1_button3

    @service1_button3.setter
    def service1_button3(self, value):
        if self._service1_button3 is None:
            self._service1_button3 = value

    @property
    def service1_textarea1(self):
        return self._service1_textarea1

    @service1_textarea1.setter
    def service1_textarea1(self, value):
        if self._service1_textarea1 is None:
            self._service1_textarea1 = value

    # endregion -------------------------------------------------------------------------------------------------------

    # region app ------------------------------------------------------------------------------------------------------
    def create_app(self) -> None:
        """Create the NiceGUI application"""
        ui.add_head_html(reset_css)

        # Create spinner first (initially hidden)
        self._spinner = ui.spinner(size='lg', color='white').classes('absolute inset-0 m-auto z-50')
        self._spinner.set_visibility(False)

        # UI Layout
        with ui.column().classes('w-screen h-screen bg-gray-300 justify-start gap-0 relative'):
            ui.label(self._title).classes('w-full p-4 text-center text-2xl font-bold border border-white')

            with ui.column().classes('w-[calc(100%-2rem)] mx-auto p-4 gap-4 bg-gray-400 border-2 border-white rounded-lg shadow-lg overflow-auto items-start'):
                self.service1_label = ui.label('1. Api Gateway Service').classes('w-1/2 p-4 text-center text-xl font-bold border border-white')

                # Fixed: Remove lambda or add parentheses
                self.service1_button1 = ui.button('Health Check', on_click=self.click_button1).classes(
                    'w-1/2 h-12 bg-blue-500 text-white rounded-lg shadow-md')

                self.service1_button2 = ui.button('Button 2', on_click=lambda: self.click(2)).classes(
                    'w-1/2 h-12 bg-blue-500 text-white rounded-lg shadow-md')

                self.service1_button3 = ui.button('Button 3', on_click=lambda: self.click(3)).classes(
                    'w-1/2 h-12 bg-blue-500 text-white rounded-lg shadow-md')

                self.service1_textarea1 = ui.textarea(label="Response").classes('border border-white w-full h-40')

    # endregion -------------------------------------------------------------------------------------------------------

    # region service1 event handlers ----------------------------------------------------------------------------------
    async def click_button1(self):
        """Health check button handler"""
        await self._base_request_handler('get', 'http://127.0.0.1:8000/health')

    async def click(self, nr):
        """Generic button handler with simulated delay"""
        self._spinner.set_visibility(True)
        self._disable_buttons(True)

        await asyncio.sleep(2.0)  # Non-blocking async sleep

        self.service1_textarea1.set_value(f'button {nr} pressed')
        self._spinner.set_visibility(False)
        self._disable_buttons(False)

    # endregion -------------------------------------------------------------------------------------------------------


if __name__ in {"__main__", "__mp_main__"}:
    dashboard = MainApp()
    ui.run(title="AegisAI", port=8080, reload=True)
