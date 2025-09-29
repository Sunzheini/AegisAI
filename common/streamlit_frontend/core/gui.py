from time import sleep

import streamlit as st


class StreamlitFrontend:
    def __init__(self):
        self._initialize_frontend()

    def _handle_button_1(self):
        st.session_state['processing'] = True
        with st.spinner("Working..."):
            try:
                sleep(3)  # Simulate work
                st.session_state['button_1_task_complete'] = True
            except Exception as e:
                st.error(f"Error during execution: {e}")
                st.session_state['button_1_task_complete'] = False
            finally:
                st.session_state['processing'] = False
                st.rerun()  # Refresh UI to show updated state

    def _initialize_frontend(self):
        # State management ------------------------------------------------
        if 'processing' not in st.session_state:
            st.session_state['processing'] = False
        if 'button_1_task_complete' not in st.session_state:
            st.session_state['button_1_task_complete'] = False

        # Content ---------------------------------------------------------
        st.header("Example frontend")
        st.subheader("Login")
        prompt = st.text_input(label="Prompt", placeholder="Enter your prompt:")

        # Buttons ---------------------------------------------------------
        row1_col1, row1_col2 = st.columns([1, 2])
        with row1_col1:
            button1 = st.button("Ingest", disabled=st.session_state['processing'])
        with row1_col2:
            button2 = st.button("Empty", disabled=st.session_state['processing'])

        # Handlers --------------------------------------------------------
        if button1 and not st.session_state['processing']:
            self._handle_button_1()

        # Status messages -------------------------------------------------
        if st.session_state.processing:
            st.warning("Operation in progress...")

        # Show success messages AFTER processing completes
        if st.session_state.get('button_1_task_complete'):
            st.success("Button1 task complete!")
            st.balloons()
            st.session_state['button_1_task_complete'] = False  # Reset
