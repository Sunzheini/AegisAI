import asyncio

import streamlit as st


class StreamlitFrontend:
    def __init__(self):
        self._initialize_frontend()

    def _generate_llm_response(self, user_prompt, chat_history):
        response = []
        return response

    def _run_tests(self, test_path=None, test_name=None):
        pass

    def _run_specific_test(self, test_function_name):
        return test_function_name

    def _run_all_tests(self):
        pass

    def _initialize_frontend(self):
        st.header ("CustomLLM Project")

        prompt = st.text_input(
            "Prompt",                           # label
            placeholder="Enter your prompt:"    # placeholder text
        )

        # Buttons ----------------------------------------------------------
        st.subheader("Data Operations")
        row1_col1, row1_col2, = st.columns([1, 2])  # 2nd takes 2x space
        with row1_col1:
            button1 = st.button("Ingest")

        with row1_col2:
            button2 = st.button("Clean")

        row2_col1, row2_col2 = st.columns([2, 2])
        with row2_col1:
            button3 = st.button("Ask")

        # Test Operations --------------------------------------------------
        st.subheader("Test Operations")

        # Test selection
        test_options = {
            "All Tests": "run_all",
            "Specific Test": "custom"
        }

        selected_test = st.selectbox("Select Test to Run", list(test_options.keys()))

        custom_test_name = ""
        if selected_test == "Specific Test":
            custom_test_name = st.text_input("Enter test function name (e.g., test_09_...):")

        # Test execution buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            run_test_button = st.button("🚀 Run Test")
        with col2:
            run_all_tests_button = st.button("🧪 Run All Tests")
        with col3:
            clear_test_output = st.button("Clear Test Output")

        # State management ------------------------------------------------
        if 'prompt_history' not in st.session_state:
            st.session_state['prompt_history'] = []

        if 'answer_history' not in st.session_state:
            st.session_state['answer_history'] = []

        if 'chat_history' not in st.session_state:
            st.session_state['chat_history'] = []   # (user, bot) tuples

        if 'processing' not in st.session_state:
            st.session_state['processing'] = False

        if 'test_results' not in st.session_state:
            st.session_state['test_results'] = None

        if 'test_output' not in st.session_state:
            st.session_state['test_output'] = ""

        # Handles ----------------------------------------------------
        # Handle button2, ingest data
        if button1:
            with st.spinner("Ingesting data..."):
                try:
                    asyncio.run(self.backend.crawled_cloud_async_ingestion())

                    st.success("Ingestion complete!")
                    st.balloons()

                except Exception as e:
                    st.error(f"Error during ingestion: {e}")

        # Handle button4, clean up data
        if button2:
            with st.spinner("Cleaning up data..."):
                try:
                    self.backend.cleanup_data()

                    st.success("Cleanup complete!")
                    st.balloons()

                except Exception as e:
                    st.error(f"Error during cleanup: {e}")

        # Handle button click and prompt submission
        if button3 and prompt:
            st.session_state['processing'] = True

            with st.spinner("Processing..."):
                try:
                    generated_response = self._generate_llm_response(prompt, chat_history=st.session_state['chat_history'])

                    st.session_state['prompt_history'].append(prompt)
                    st.session_state['answer_history'].append(generated_response)

                    st.session_state['chat_history'].append(('human', prompt))
                    st.session_state['chat_history'].append(('ai', generated_response['result']))

                    st.success("Done!")
                    st.balloons()

                except Exception as e:
                    st.error(f"Error: {e}")

                finally:
                    st.session_state['processing'] = False

        # Handle test execution
        if run_test_button:
            st.session_state['processing'] = True
            with st.spinner("Running test..."):
                try:
                    if selected_test == "All Tests" or run_all_tests_button:
                        result = self._run_all_tests()
                    elif selected_test == "Specific Test" and custom_test_name:
                        result = self._run_specific_test(custom_test_name)
                    else:
                        test_function_name = test_options[selected_test]
                        result = self._run_specific_test(test_function_name)

                    st.session_state['test_results'] = result

                    # Display results
                    if result['success']:
                        st.success("✅ Tests passed!")
                    else:
                        st.error("❌ Tests failed!")

                    # Show test output in expandable section
                    with st.expander("Test Output", expanded=True):
                        st.text_area("Output", result['stdout'] + "\n" + result['stderr'], height=300)

                except Exception as e:
                    st.error(f"Error running tests: {e}")
                finally:
                    st.session_state['processing'] = False

        # Handle "Run All Tests" button
        if run_all_tests_button:
            st.session_state['processing'] = True
            with st.spinner("Running all tests..."):
                try:
                    result = self._run_all_tests()
                    st.session_state['test_results'] = result

                    if result['success']:
                        st.success("✅ All tests passed!")
                    else:
                        st.error("❌ Some tests failed!")

                    with st.expander("Test Output", expanded=True):
                        st.text_area("Output", result['stdout'] + "\n" + result['stderr'], height=300)

                except Exception as e:
                    st.error(f"Error running tests: {e}")
                finally:
                    st.session_state['processing'] = False

        # Handle clear test output
        if clear_test_output:
            st.session_state['test_results'] = None
            st.session_state['test_output'] = ""
            st.rerun()

        # Display chat messages from history on app rerun
        if st.session_state['answer_history']:
            for generated_response, prompt in zip(st.session_state['answer_history'], st.session_state['prompt_history']):
                st.chat_message("user").write(prompt)
                st.chat_message("assistant").write(generated_response['result'])
