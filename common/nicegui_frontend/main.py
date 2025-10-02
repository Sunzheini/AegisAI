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
        """Base async request handler"""
        self._spinner.set_visibility(True)
        self._disable_buttons(True)

        try:
            async with aiohttp.ClientSession() as session:
                # Prepare request
                request_kwargs = {}

                # If POST then add data
                if method_type == 'post':
                    # Special handling for login endpoint
                    if url.endswith('/auth/login') and data:
                        request_kwargs['data'] = data

                    # Add auth header for non-login requests
                    else:
                        if self._access_token:
                            if headers is None:
                                headers = {}
                            headers['Authorization'] = f'Bearer {self._access_token}'
                        request_kwargs['json'] = data

                # Add headers if provided
                if headers:
                    request_kwargs['headers'] = headers

                # Make request
                async with getattr(session, method_type)(url, **request_kwargs) as response:
                    # Process response
                    try:
                        response_data = await response.json()
                        display_content = json.dumps(response_data, indent=4)

                        # Handle token storage
                        if response.status == 200 and url.endswith('/auth/login') and 'access_token' in response_data:
                            self._access_token = response_data['access_token']
                            ui.notify("Login successful! Token stored.")

                    except (aiohttp.ContentTypeError, json.JSONDecodeError):
                        display_content = await response.text()

                    self.service1_textarea1.set_value(f"Status: {response.status}\n{display_content}")

        except Exception as e:
            ui.notify(f"Error during execution: {str(e)}")
            self.service1_textarea1.set_value(f"Error: {str(e)}")

        finally:
            self._spinner.set_visibility(False)
            self._disable_buttons(False)

    # endregion -------------------------------------------------------------------------------------------------------

    # region app ------------------------------------------------------------------------------------------------------
    def create_app(self) -> None:
        """Create the NiceGUI application"""
        ui.add_head_html(reset_css)

        # Create spinner first (initially hidden)
        self._spinner = ui.spinner(size='lg', color='white').classes('absolute inset-0 m-auto z-50')
        self._spinner.set_visibility(False)

        # Overall Container
        with ui.column().classes('w-screen h-screen gap-0 '
                                 'bg-gray-300 '
                                 'justify-start relative'):

            # Title
            ui.label(self._title).classes('w-full p-4 text-center text-2xl font-bold border border-white')

            # Service 1: API Gateway Container
            with ui.column().classes(
                    'w-2/5 h-4/5 mx-auto p-4 gap-4 '
                    'bg-gray-400 border-2 border-white rounded-lg shadow-lg '
                    'overflow-auto items-start'):

                # Service 1 Label
                self.service1_label = ui.label('1. Api Gateway Service').classes(
                    'w-full p-4 '
                    'text-center text-xl font-bold border border-white')

                # Service 1 Button Group1 Container
                with ui.row().classes(
                        'w-full gap-4 '
                        'border border-white '
                        'items-center justify-evenly'):

                    # Service 1 Button1 - Health Check
                    self.service1_button1 = ui.button('Health Check', on_click=self._health_check).classes(
                        'w-2/5 h-8 '
                        'bg-blue-500 text-white rounded-lg shadow-md')

                    # Service 1 Button2 - Empty
                    self.service1_button2 = ui.button('Empty', on_click=None).classes(
                        'w-2/5 h-8 '
                        'bg-blue-500 text-white rounded-lg shadow-md')
                    self.service1_button2.disable()

                # Service 1 Input - Username
                self._service1_input1 = ui.input(label="Username").classes(
                    'w-full h-16 '
                    'border border-white')

                # Service 1 Input - Password
                self._service1_input2 = ui.input(label="Password").classes(
                    'w-full h-16 '
                    'border border-white')

                # Service 1 Button Group2 Container
                with ui.row().classes(
                        'w-full gap-4 '
                        'border border-white '
                        'items-center justify-evenly'):

                    # Service 1 Button3 - Login and store token
                    self.service1_button3 = ui.button('Login and Store Token', on_click=self._login_and_store_token).classes(
                        'w-2/5 h-8 '
                        'bg-blue-500 text-white rounded-lg shadow-md')

                    # Service 1 Button4 - Logout and delete token on client side
                    self.service1_button4 = ui.button('Logout and Delete Token', on_click=self._logout_and_delete_token).classes(
                        'w-2/5 h-8 '
                        'bg-blue-500 text-white rounded-lg shadow-md')

                # Service 1 Button Group3 Container
                with ui.row().classes(
                        'w-full gap-4 '
                        'border border-white '
                        'items-center justify-evenly'):

                    # Service 1 Button5 - GET users list
                    self.service1_button5 = ui.button('Get users list', on_click=self._get_users_list).classes(
                        'w-2/5 h-8 '
                        'bg-blue-500 text-white rounded-lg shadow-md')

                    # Service 1 Button6 - Empty
                    self.service1_button6 = ui.button('Empty', on_click=None).classes(
                        'w-2/5 h-8 '
                        'bg-blue-500 text-white rounded-lg shadow-md')
                    self.service1_button6.disable()

                # Service 1 Textarea - Response display
                self.service1_textarea1 = ui.textarea(label="Response").classes(
                    'w-full h-auto '
                    'border border-white')
                self.service1_textarea1.props('readonly')

    # endregion -------------------------------------------------------------------------------------------------------

    # region service1 event handlers ----------------------------------------------------------------------------------
    async def _health_check(self):
        """Health check button handler"""
        await self._base_request_handler('get', 'http://127.0.0.1:8000/health')

    async def _login_and_store_token(self):
        """Login button handler"""
        username = self._service1_input1.value
        password = self._service1_input2.value

        if not username or not password:
            ui.notify("Please enter both username and password.")
            return

        data = {'username': username.strip(), 'password': password.strip()}

        # For OAuth2 login, we send as form data (not JSON)
        await self._base_request_handler('post', 'http://127.0.0.1:8000/auth/login', data=data)

    async def _logout_and_delete_token(self):
        """Logout button handler"""

        if not self._access_token:
            ui.notify("No token found. Please login first.")
            self.service1_textarea1.set_value("No token found. Please login first.")
            return

        headers = {"Authorization": f"Bearer {self._access_token}"}
        await self._base_request_handler('post', 'http://127.0.0.1:8000/auth/logout', headers=headers)

        self._access_token = None
        ui.notify("Logged out and token deleted.")
        self.service1_textarea1.set_value("Logged out. Token deleted.")

    async def _get_users_list(self):
        """Get users list button handler"""
        if not self._access_token:
            ui.notify("Please login first to obtain an access token.")
            return

        headers = {"Authorization": f"Bearer {self._access_token}"}
        await self._base_request_handler('get', 'http://127.0.0.1:8000/users/list', headers=headers)

    # endregion -------------------------------------------------------------------------------------------------------


if __name__ in {"__main__", "__mp_main__"}:
    dashboard = MainApp()
    ui.run(title="AegisAI", port=8080, reload=True)
