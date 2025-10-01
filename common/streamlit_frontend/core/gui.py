import json
import streamlit as st
import requests


class StreamlitFrontend:
    def __init__(self):
        self._initialize_frontend()

    def _base_handle(self, method_type: str, url: str, data=None, headers=None):
        st.session_state['processing'] = True
        with st.spinner("Working..."):
            try:
                if method_type == 'get':
                    result = requests.get(url, headers=headers)
                    st.text(f"Status Code: {result.status_code}")
                    if result.status_code == 200:
                        response_data = result.json()
                        # Store token if this is a login response
                        if url.endswith('/auth/login') and 'access_token' in response_data:
                            st.session_state['access_token'] = response_data['access_token']
                            st.success("Login successful! Token stored.")
                    else:
                        st.error(f"Error: {result.status_code} - {result.text}")

                elif method_type == 'post':
                    # For login endpoint, ensure data is sent as form data
                    if url.endswith('/auth/login') and data:
                        result = requests.post(url, data=data)
                    else:
                        result = requests.post(url, json=data, headers=headers)

                    st.text(f"Status Code: {result.status_code}")
                    if result.status_code == 200:
                        response_data = result.json()
                        st.text(json.dumps(response_data, indent=4))
                        # Store token if this is a login response
                        if url.endswith('/auth/login') and 'access_token' in response_data:
                            st.session_state['access_token'] = response_data['access_token']
                            st.success("Login successful! Token stored.")

                            # Force a rerun to show the new buttons
                            st.rerun()
                    else:
                        st.error(f"Error: {result.status_code} - {result.text}")
                else:
                    st.error(f"Unsupported method type: {method_type}")

            except Exception as e:
                st.error(f"Error during execution: {e}")
            finally:
                st.session_state['processing'] = False

    def _handle_button_1(self):
        self._base_handle('get', 'http://127.0.0.1:8000/health')

    def _handle_button_2(self):
        self._base_handle('get', 'http://127.0.0.1:8000/health')

    def _handle_button_3(self):
        username = st.session_state.get('username_input', '')
        password = st.session_state.get('password_input', '')

        if not username or not password:
            st.error("Please enter both username and password")
            return

        # Use the exact format that OAuth2PasswordRequestForm expects
        login_data = {
            'username': username.strip(),
            'password': password.strip()
        }

        # For OAuth2 login, we send as form data (not JSON)
        self._base_handle('post', 'http://127.0.0.1:8000/auth/login', data=login_data)

    def _handle_button_4(self):
        self._base_handle('get', 'http://127.0.0.1:8000/health')

    def _initialize_frontend(self):
        # State management ------------------------------------------------
        if 'processing' not in st.session_state:
            st.session_state['processing'] = False
        if 'access_token' not in st.session_state:
            st.session_state['access_token'] = None

        # Content ---------------------------------------------------------
        st.header("Example frontend")
        st.subheader("General")

        # Row1 ------------------------------------------------------------
        row1_col1, row1_col2 = st.columns([1, 2])
        with row1_col1:
            button1 = st.button("Health", disabled=st.session_state['processing'])
        with row1_col2:
            button2 = st.button("Empty", disabled=st.session_state['processing'])

        # Row2 ------------------------------------------------------------
        # Use unique keys for the inputs
        username = st.text_input(
            label="username",
            placeholder="Enter your username:",
            key='username_input'
        )
        password = st.text_input(
            label="password",
            placeholder="Enter your password:",
            type="password",
            key='password_input'
        )

        row2_col1, row2_col2 = st.columns([1, 2])
        with row2_col1:
            button3 = st.button("Login and get token", disabled=st.session_state['processing'])
        with row2_col2:
            button4 = st.button("Register", disabled=st.session_state['processing'])

        # Display token if available
        if st.session_state.get('access_token'):
            st.success("✅ Logged in successfully!")
            st.text_area("Access Token", st.session_state['access_token'], height=100)

            # Add a button to test protected endpoint
            st.subheader("Test Protected Endpoints")
            if st.button("Test /list endpoint (protected)"):
                headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}
                self._base_handle('get', 'http://127.0.0.1:8000/users/list', headers=headers)

        # Handlers --------------------------------------------------------
        if button1 and not st.session_state['processing']:
            self._handle_button_1()

        if button2 and not st.session_state['processing']:
            self._handle_button_2()

        if button3 and not st.session_state['processing']:
            self._handle_button_3()

        if button4 and not st.session_state['processing']:
            self._handle_button_4()

        # Status messages -------------------------------------------------
        if st.session_state.processing:
            st.warning("Operation in progress...")

        # Footer ----------------------------------------------------------
        st.markdown("---")

        # Optional: Add logout button
        if st.session_state.get('access_token'):
            if st.button("Logout"):
                st.session_state['access_token'] = None
                st.success("Logged out successfully!")
                st.rerun()
