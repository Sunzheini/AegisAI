"""
NiceGUI frontend for AegisAI microservices showcase
"""
import os
import asyncio
import json
import aiohttp  # async HTTP client instead of requests!

from dotenv import load_dotenv
from nicegui import ui
from support.reset_css_for_nicegui import RESET_CSS

load_dotenv()


class MainApp:
    """Main NiceGUI application class"""
    def __init__(self):
        # Service URLs (configurable via environment variables for Kubernetes)
        self.api_gateway_url = os.getenv("API_GATEWAY_URL", "http://127.0.0.1:8000")

        # general
        self._title = "AegisAI Microservices Showcase"
        self._spinner = None
        self._access_token = None
        self._form_is_visible = False
        self.uploaded_file_info = None

        self._polling_active = False
        self._polling_job_id = None

        # AI Summary display
        self.ai_summary_container = None
        self.ai_summary_text = None

        # AI Chat state
        self.chat_history = []
        self.chat_container = None
        self.chat_input = None
        self.chat_messages_container = None

        self.create_app()

    # region general methods ----------------------------------------------------------------------
    def _disable_all_service1_buttons(self, disable: bool) -> None:
        """Enable or disable all buttons for service1"""
        for i in range(1, 4):
            button = getattr(self, f"_service1_button{i}", None)
            if button:
                if disable:
                    button.props("disable")
                    button.classes("opacity-50 cursor-not-allowed")
                else:
                    button.props(remove="disable")
                    button.classes(remove="opacity-50 cursor-not-allowed")

    async def _poll_job_status(self, job_id, context) -> None:
        """
        Poll the job status endpoint until job is completed or failed.
        The orchestrator is expected to be running on localhost:9000 or via Kubernetes service.
        :param job_id: the job ID to poll
        :param context: NiceGUI context manager for UI updates
        """
        # Get orchestrator URL from environment (Kubernetes service name or localhost)
        orchestrator_url = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:9000")
        url = f"{orchestrator_url}/jobs/{job_id}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        with context:
            self.ai_summary_container.classes("block").classes(remove="hidden")
            self.ai_summary_text.set_value("🔄 Starting document processing pipeline...")

        max_attempts = 120
        attempt = 0
        ai_data_found = False

        while attempt < max_attempts and not ai_data_found:
            await asyncio.sleep(2)
            attempt += 1

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status != 200:
                            with context:
                                self.ai_summary_text.set_value(f"❌ HTTP Error: {response.status}")
                            continue

                        resp_json = await response.json()
                        status = resp_json.get("status")
                        step = resp_json.get("step", "")

                        print(f"[DEBUG] Polling attempt {attempt}: status={status}, step={step}")
                        print(f"[DEBUG] Full response keys: {list(resp_json.keys())}")

                        # Update textarea with status
                        with context:
                            self.service1_textarea1.set_value(
                                f"Polling job {job_id}... (Attempt {attempt}/{max_attempts})\n"
                                f"Status: {status}\nStep: {step}\n"
                                f"Response: {json.dumps(resp_json, indent=4)}"
                            )

                            # Extract and display AI summary
                            ai_summary = self._extract_ai_summary(resp_json)
                            self.ai_summary_text.set_value(ai_summary)

                        # Check if we have AI processing data in metadata
                        metadata = resp_json.get('metadata', {})
                        if metadata is None:
                            metadata = {}

                        # Look for AI processing data
                        ai_processing = metadata.get('ai_processing')
                        if ai_processing:
                            print(f"[DEBUG] ✅ AI processing data found! Stopping polling.")
                            ai_data_found = True
                            with context:
                                ui.notify(f"✅ Job {job_id} completed with AI analysis!")
                            break

                        # Also stop if job failed
                        elif status == "failed":
                            with context:
                                ui.notify(f"❌ Job {job_id} failed!")
                                self.ai_summary_text.set_value(f"❌ Job failed at step: {step}")
                            return

                        # Continue polling if we're still processing
                        print(f"[DEBUG] No AI data yet, continuing to poll...")

            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
                with context:
                    ui.notify(f"Polling failed: {str(e)}")
                    self.ai_summary_text.set_value(f"❌ Polling error: {str(e)}")
                return
            except Exception as e:
                with context:
                    ui.notify(f"Unexpected error during polling: {str(e)}")
                    self.ai_summary_text.set_value(f"❌ Unexpected error: {str(e)}")
                return

        if not ai_data_found:
            # Timeout or completed without AI data
            with context:
                ui.notify(f"⏰ Polling ended for job {job_id}")
                self.ai_summary_text.set_value(
                    f"⏰ Processing ended after {attempt} attempts\n\n"
                    f"Last status: {status if 'status' in locals() else 'unknown'}\n"
                    f"Last step: {step if 'step' in locals() else 'unknown'}\n\n"
                    f"AI analysis data was not found in the response."
                )

    async def _base_request_handler(self, method_type: str, url: str, data=None, headers=None) -> None:
        """
        Base async request handler
        :param method_type: HTTP method type (get, post, put, delete)
        :param url: the URL to send the request to
        :param data: the data to send (for POST/PUT)
        :param headers: optional headers to include
        """
        self._spinner.set_visibility(True)
        self._disable_all_service1_buttons(True)

        try:
            async with aiohttp.ClientSession() as session:
                # Prepare request
                request_kwargs = {}

                # If POST then add data
                if method_type == "post":
                    # Special handling for login endpoint
                    if url.endswith("/auth/login") and data:
                        request_kwargs["data"] = data

                    # Add auth header for non-login requests
                    else:
                        if self._access_token:
                            if headers is None:
                                headers = {}
                            headers["Authorization"] = f"Bearer {self._access_token}"
                        request_kwargs["json"] = data

                # Put request handling
                elif method_type == "put":
                    if self._access_token:
                        if headers is None:
                            headers = {}
                        headers["Authorization"] = f"Bearer {self._access_token}"
                    request_kwargs["json"] = data

                # Add headers if provided
                if headers:
                    request_kwargs["headers"] = headers

                # Make request
                async with getattr(session, method_type)(
                    url, **request_kwargs
                ) as response:
                    # Process response
                    try:
                        response_data = await response.json()
                        display_content = json.dumps(response_data, indent=4)

                        # Handle token storage
                        if (
                            response.status == 200
                            and url.endswith("/auth/login")
                            and "access_token" in response_data
                        ):
                            self._access_token = response_data["access_token"]
                            ui.notify("Login successful! Token stored.")

                    except (aiohttp.ContentTypeError, json.JSONDecodeError):
                        display_content = await response.text()

                    self.service1_textarea1.set_value(
                        f"Status: {response.status}" f"\n{display_content}"
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            ui.notify(f"Request failed: {str(e)}")
            self.service1_textarea1.set_value(f"Request failed: {str(e)}")
        except Exception as e:
            ui.notify(f"Unexpected error during execution: {str(e)}")
            self.service1_textarea1.set_value(f"Unexpected error: {str(e)}")
        finally:
            self._spinner.set_visibility(False)
            self._disable_all_service1_buttons(False)

    # endregion -----------------------------------------------------------------------------------

    # region ai methods ---------------------------------------------------------------------------
    @staticmethod
    def _extract_ai_summary(response_data) -> str:
        """
        Extract AI summary from the response data
        :param response_data: the full response data from the job status endpoint
        """
        try:
            if not isinstance(response_data, dict):
                return "🔄 Waiting for processing data..."

            status = response_data.get('status', '')
            step = response_data.get('step', '')
            job_id = response_data.get('job_id', 'unknown')

            print(f"[EXTRACT_AI] Step: {step}, Status: {status}")
            print(f"[EXTRACT_AI] All response keys: {list(response_data.keys())}")

            # Get metadata - handle None case
            metadata = response_data.get('metadata', {})
            if metadata is None:
                metadata = {}
                print(f"[EXTRACT_AI] Metadata was None, set to empty dict")
            else:
                print(f"[EXTRACT_AI] Metadata keys: {list(metadata.keys())}")

            # Look for AI processing data - check multiple possible locations
            ai_processing = None

            # First, check the standard location
            if 'ai_processing' in metadata:
                ai_processing = metadata['ai_processing']
                print(f"[EXTRACT_AI] Found ai_processing in metadata")

            # If not found, check if any key in metadata contains AI data
            if not ai_processing:
                for key, value in metadata.items():
                    if isinstance(value, dict) and any(
                            ai_key in value for ai_key in ['document_summary', 'sentiment_analysis', 'ai_insights']):
                        ai_processing = value
                        print(f"[EXTRACT_AI] Found AI data in metadata['{key}']")
                        break

            # If still not found, check if the metadata itself contains AI data
            if not ai_processing:
                if any(ai_key in metadata for ai_key in ['document_summary', 'sentiment_analysis', 'ai_insights']):
                    ai_processing = metadata
                    print(f"[EXTRACT_AI] Found AI data directly in metadata")

            print(f"[EXTRACT_AI] AI Processing data: {ai_processing}")

            # If we found AI processing data, format it
            if ai_processing:
                print(f"[EXTRACT_AI] Formatting AI summary...")

                summary_parts = ["✅ **AI Analysis Complete**\n"]

                # Extract document summary
                doc_summary = ai_processing.get('document_summary', {})
                if not doc_summary and 'summary' in ai_processing:
                    doc_summary = ai_processing

                # Main summary
                if doc_summary.get('summary'):
                    summary_parts.append(f"📄 **Document Summary**: {doc_summary['summary']}")

                # Metrics
                metrics = []
                word_count = doc_summary.get('word_count') or ai_processing.get('word_count')
                if word_count:
                    metrics.append(f"Words: {word_count}")

                reading_time = doc_summary.get('estimated_reading_time_minutes') or ai_processing.get(
                    'estimated_reading_time_minutes')
                if reading_time:
                    metrics.append(f"Reading Time: {reading_time} min")

                content_type = doc_summary.get('content_type') or ai_processing.get('content_type')
                if content_type:
                    metrics.append(f"Type: {content_type}")

                if metrics:
                    summary_parts.append(f"📊 **Metrics**: {', '.join(metrics)}")

                # Key topics
                key_topics = doc_summary.get('key_topics') or ai_processing.get('key_topics')
                if key_topics and isinstance(key_topics, list):
                    # Clean and limit topics
                    clean_topics = []
                    for topic in key_topics[:5]:
                        if isinstance(topic, str) and len(topic) < 100:  # Reasonable length
                            clean_topics.append(topic)
                    if clean_topics:
                        summary_parts.append(f"🔑 **Key Topics**: {', '.join(clean_topics)}")

                # AI insights
                ai_insights = ai_processing.get('ai_insights', {})
                insights = ai_insights.get('insights') or ai_processing.get('insights')
                if insights and isinstance(insights, list):
                    insights_text = " • " + "\n • ".join(insights)
                    summary_parts.append(f"💡 **AI Insights**:\n{insights_text}")

                # Sentiment
                sentiment_data = ai_processing.get('sentiment_analysis', {})
                sentiment = sentiment_data.get('sentiment') or ai_processing.get('sentiment')
                if sentiment:
                    sentiment_text = f"😊 **Sentiment**: {sentiment.title()}"
                    confidence = sentiment_data.get('sentiment_confidence') or ai_processing.get('sentiment_confidence')
                    if confidence:
                        sentiment_text += f" ({confidence}% confidence)"
                    summary_parts.append(sentiment_text)

                # Complexity
                complexity = ai_insights.get('overall_complexity') or ai_processing.get('overall_complexity')
                if complexity:
                    emoji = "🔴" if complexity == 'high' else "🟡" if complexity == 'medium' else "🟢"
                    summary_parts.append(f"{emoji} **Complexity**: {complexity.title()}")

                result = "\n\n".join(summary_parts)
                print(f"[EXTRACT_AI] Final summary: {result}")
                return result

            # If we're at the final step but no AI data found
            if step == "ai_processing_done" and status == "success":
                return ("✅ **Processing Complete!**\n\n"
                        "The document has been successfully processed through the AI pipeline.\n\n"
                        f"Job ID: {job_id}")

            # Progress messages
            progress_messages = {
                'queued': '🔄 Job queued and waiting to start processing...',
                'validate_file': '🔍 Validating file format, size, and integrity...',
                'extract_metadata': '📊 Extracting document metadata and properties...',
                'extract_text': '📝 Extracting text content from document...',
                'ai_processing': '🤖 Running AI analysis...',
                'ai_processing_done': '✅ AI processing complete! Finalizing results...',
            }

            current_message = progress_messages.get(step, f'🔄 Processing: {step.replace("_", " ").title()}...')
            return f"{current_message}\n\nJob ID: {job_id}\nStatus: {status}"

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"[EXTRACT_AI] Error: {e}\n{error_details}")
            return f"❌ Error extracting AI summary: {str(e)}"

    def _add_ai_chat_section(self) -> None:
        """Add AI Chat section to the frontend"""
        with ui.column().classes(
                "w-full h-auto p-4 gap-4 "
                "border-2 border-white rounded-lg bg-gray-200"
        ) as self.chat_container:
            ui.label("💬 AI Chat - Ask Questions About Your Document").classes(
                "w-full p-2 text-center text-xl font-bold border border-white bg-gray-300"
            )

            # Chat messages area
            with ui.scroll_area().classes(
                    "w-full h-64 border border-gray-300 bg-white rounded-lg") as self.chat_messages_container:
                # Messages will be added here dynamically
                ui.label("Start a conversation about your uploaded document...").classes(
                    "w-full p-2 text-gray-500 text-center")

            # Chat input area
            with ui.row().classes("w-full gap-2 items-center"):
                self.chat_input = ui.input(placeholder="Ask a question about your document...").classes("flex-grow")
                ui.button("Send", on_click=self._send_chat_message).classes("bg-green-500 text-white")
                ui.button("Clear Chat", on_click=self._clear_chat).classes("bg-red-500 text-white")

    async def _send_chat_message(self) -> None:
        """Send chat message to AI service"""
        message = self.chat_input.value.strip()
        if not message:
            ui.notify("Please enter a message")
            return

        if not self.uploaded_file_info:
            ui.notify("Please upload a document first")
            return

        # Disable input during processing
        self.chat_input.disable()
        self._spinner.set_visibility(True)

        try:
            # Add user message to chat
            self._add_chat_message("user", message)
            self.chat_input.set_value("")

            # Send request to AI service
            # Get AI service URL from environment (Kubernetes service name or localhost)
            ai_service_url = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:9004")

            payload = {
                "user_prompt": message,
                "chat_history": self.chat_history
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{ai_service_url}/generate-response",
                        json=payload
                ) as response:
                    result = await response.json()

                    if "error" in result:
                        self._add_chat_message("error", f"Error: {result['error']}")
                    else:
                        # Add AI response
                        self._add_chat_message("ai", result["result"])
                        # Update chat history
                        self.chat_history = result.get("chat_history", [])
                        ui.notify("✅ Response received!")

        except Exception as e:
            self._add_chat_message("error", f"Request failed: {str(e)}")
            ui.notify(f"❌ Chat request failed: {str(e)}")
        finally:
            self.chat_input.enable()
            self._spinner.set_visibility(False)

    def _add_chat_message(self, sender, message) -> None:
        """
        Add a message to the chat UI
        :param sender: "user", "ai", or "error"
        :param message: the message content
        """
        if sender == "user":
            with self.chat_messages_container:
                with ui.row().classes("w-full justify-end"):
                    with ui.column().classes("max-w-3/4 bg-blue-100 p-3 rounded-lg"):
                        ui.label("👤 You").classes("text-sm font-bold")
                        ui.label(message).classes("text-gray-800")
        elif sender == "ai":
            with self.chat_messages_container:
                with ui.row().classes("w-full justify-start"):
                    with ui.column().classes("max-w-3/4 bg-green-100 p-3 rounded-lg"):
                        ui.label("🤖 AI").classes("text-sm font-bold")
                        ui.label(message).classes("text-gray-800")
        else:  # error
            with self.chat_messages_container:
                with ui.row().classes("w-full justify-center"):
                    with ui.column().classes("max-w-3/4 bg-red-100 p-3 rounded-lg"):
                        ui.label("❌ Error").classes("text-sm font-bold text-red-600")
                        ui.label(message).classes("text-red-700")

    def _clear_chat(self) -> None:
        """Clear chat history"""
        self.chat_history = []
        self.chat_messages_container.clear()
        self.chat_messages_container.add(
            ui.label("Chat cleared. Start a new conversation...").classes("w-full p-2 text-gray-500 text-center"))
        ui.notify("Chat cleared")

    async def _cleanup_data(self) -> None:
        """Cleanup Pinecone data"""
        try:
            # Get AI service URL from environment
            ai_service_url = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:9004")

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{ai_service_url}/clean") as response:
                    # First, check if we got a successful response
                    if response.status == 200:
                        result = await response.json()

                        # Handle the response based on content
                        if result and "success" in result and result["success"]:
                            message = result.get("message", "Data cleaned successfully!")
                            ui.notify(f"✅ {message}")

                            # Format the results nicely
                            results_text = f"Cleanup completed:\n"
                            if "results" in result:
                                for index_name, status in result["results"].items():
                                    results_text += f"• {index_name}: {status}\n"

                            self.service1_textarea1.set_value(results_text)
                        else:
                            error_msg = result.get("error", "Unknown error occurred") if result else "No response data"
                            ui.notify(f"❌ Cleanup failed: {error_msg}")
                            self.service1_textarea1.set_value(f"Cleanup failed: {error_msg}")

                    else:
                        # Handle non-200 status codes
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get("error", f"HTTP {response.status}")
                        except:
                            error_msg = f"HTTP {response.status}"

                        ui.notify(f"❌ Cleanup failed: {error_msg}")
                        self.service1_textarea1.set_value(f"Cleanup failed: {error_msg}")

        except Exception as e:
            ui.notify(f"❌ Cleanup request failed: {str(e)}")
            self.service1_textarea1.set_value(f"Cleanup request failed: {str(e)}")

    async def _run_tests(self) -> None:
        """Run tests via AI service"""
        try:
            # Get AI service URL from environment
            ai_service_url = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:9004")

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{ai_service_url}/run-tests") as response:
                    result = await response.json()

                    if result.get("success"):
                        ui.notify("✅ Tests passed!")
                    else:
                        ui.notify("❌ Tests failed!")

                    self.service1_textarea1.set_value(
                        f"Test Results:\nSuccess: {result.get('success', False)}\n\n"
                        f"STDOUT:\n{result.get('stdout', '')}\n\n"
                        f"STDERR:\n{result.get('stderr', '')}\n\n"
                        f"Error: {result.get('error', 'None')}"
                    )

        except Exception as e:
            ui.notify(f"Test execution failed: {str(e)}")

    # endregion -----------------------------------------------------------------------------------

    # region app ----------------------------------------------------------------------------------
    def create_app(self) -> None:
        """Create the NiceGUI application"""
        ui.add_head_html(RESET_CSS)

        # Create spinner first (initially hidden)
        self._spinner = ui.spinner(size="lg", color="white").classes(
            "absolute inset-0 m-auto z-50"
        )
        self._spinner.set_visibility(False)

        # Overall Container
        with ui.column().classes(
            "w-screen h-screen gap-0 bg-gray-300 justify-start relative"
        ):

            # Title
            ui.label(self._title).classes(
                "w-full p-4 text-center text-2xl font-bold border border-white"
            )

            # Main content area with scroll
            with ui.scroll_area().classes("w-full flex-grow"):
                with ui.column().classes("w-3/4 mx-auto p-4 gap-0 flex-row"):

                    # Service 1: API Gateway Container
                    with ui.column().classes(
                        "w-2/5 h-auto mx-auto p-4 gap-4 "
                        "bg-gray-400 border-2 border-white rounded-lg shadow-lg "
                        "overflow-auto items-start"
                    ):

                        # Service 1 Label
                        self.service1_label = ui.label("Gateway Service").classes(
                            "w-full p-4 text-center text-xl font-bold border border-white"
                        )

                        # Service 1 Button Group1 Container
                        with ui.row().classes(
                            "w-full gap-4 border border-white items-center justify-evenly"
                        ):

                            # Service 1 Button1 - Health Check
                            self.service1_button1 = ui.button(
                                "Health Check", on_click=self._health_check
                            ).classes(
                                "w-2/5 h-8 bg-blue-500 text-white rounded-lg shadow-md"
                            )

                            # Service 1 Button2 - Empty
                            self.service1_button2 = ui.button("Empty", on_click=None).classes(
                                "w-2/5 h-8 bg-blue-500 text-white rounded-lg shadow-md"
                            )
                            self.service1_button2.disable()

                        # Service 1 Input 1 - Username
                        self._service1_input1 = ui.input(label="Username").classes(
                            "w-full h-16 border border-white"
                        )

                        # Service 1 Input 2 - Password
                        self._service1_input2 = ui.input(label="Password").classes(
                            "w-full h-16 border border-white"
                        )

                        # Service 1 Button Group2 Container
                        with ui.row().classes(
                            "w-full gap-4 border border-white items-center justify-evenly"
                        ):

                            # Service 1 Button3 - Login and store token
                            self.service1_button3 = ui.button(
                                "Login and Store Token", on_click=self._login_and_store_token
                            ).classes(
                                "w-2/5 h-8 bg-blue-500 text-white rounded-lg shadow-md"
                            )

                            # Service 1 Button4 - Logout and delete token on client side
                            self.service1_button4 = ui.button(
                                "Logout and Delete Token",
                                on_click=self._logout_and_delete_token,
                            ).classes(
                                "w-2/5 h-8 bg-blue-500 text-white rounded-lg shadow-md"
                            )

                        # Service 1 Button Group3 Container
                        with ui.row().classes(
                            "w-full gap-4 border border-white items-center justify-evenly"
                        ):

                            # Service 1 Button5 - GET users list
                            self.service1_button5 = ui.button(
                                "Get users list", on_click=self._get_users_list
                            ).classes(
                                "w-2/5 h-8 bg-blue-500 text-white rounded-lg shadow-md"
                            )

                            # Service 1 Button6 - Empty
                            self.service1_button6 = ui.button("Empty", on_click=None).classes(
                                "w-2/5 h-8 bg-blue-500 text-white rounded-lg shadow-md"
                            )
                            self.service1_button6.disable()

                        # Service 1 Combo Group1 Container
                        with ui.row().classes(
                            "w-full gap-4 border border-white items-center justify-start"
                        ):

                            # Service 1 Input 3 - ID
                            self._service1_input3 = ui.input(label="ID").classes("w-w-2/5 h-16")

                            # Service 1 Button7 - GET user by ID
                            self.service1_button7 = ui.button(
                                "Get User by ID", on_click=self._get_user_by_id
                            ).classes(
                                "w-2/5 h-8 ml-[355px] "
                                "bg-blue-500 text-white rounded-lg shadow-md"
                            )

                        # Toggle to show form below
                        self.form_switch = ui.switch("Toggle form")
                        self.form_switch.on("click", lambda e: self._toggle_form())

                        # Service 1 Form Group1 Container
                        with ui.column().classes(
                            "w-full h-auto p-4 gap-4 "
                            "border border-white rounded-lg bg-gray-200 hidden"
                        ) as self.user_form_container:
                            self.user_form_name = ui.input(label="Name").classes("w-full")
                            self.user_form_age = (
                                ui.input(label="Age").props("type=number").classes("w-full")
                            )
                            self.user_form_city = ui.input(label="City").classes("w-full")
                            self.user_form_email = ui.input(label="Email").classes("w-full")
                            self.user_form_password = ui.input(
                                label="Password", password=True
                            ).classes("w-full")

                            with ui.row().classes("w-full mt-4 gap-4 justify-evenly"):
                                ui.button("Create User", on_click=self._create_user).classes(
                                    "w-1/4 bg-green-500 text-white rounded-lg"
                                )
                                ui.button("Edit User", on_click=self._edit_user).classes(
                                    "w-1/4 bg-yellow-500 text-white rounded-lg"
                                )
                                ui.button("Delete User", on_click=self._delete_user).classes(
                                    "w-1/4 bg-red-500 text-white rounded-lg"
                                )

                        # File Upload Section
                        with ui.column().classes(
                            "w-full h-auto p-4 gap-4 "
                            "border border-white rounded-lg bg-gray-200"
                        ):
                            self.uploaded_file_info = None
                            self.uploaded_file = ui.upload(
                                label="Select file to upload",
                                auto_upload=True,  # Upload immediately when file is selected
                                multiple=False,
                                on_upload=self._on_file_selected,
                            ).classes("w-full")

                        # Service 1 Textarea - Response display
                        self.service1_textarea1 = ui.textarea(label="Response").classes(
                            "w-full h-auto border border-white"
                        )
                        self.service1_textarea1.props("readonly")

                    # AI Operations Section
                    with ui.column().classes(
                            "w-2/5 h-auto mx-auto p-4 gap-4 "
                            "bg-gray-400 border-2 border-white rounded-lg shadow-lg "
                            "overflow-auto items-start"
                    ):
                        ui.label("🔧 AI Operations").classes(
                            "w-full p-2 text-center text-xl font-bold border border-white bg-gray-300"
                        )

                        with ui.row().classes("w-full gap-4 justify-center"):
                            ui.button("🧹 Clean Vector Store", on_click=self._cleanup_data).classes(
                                "bg-red-500 text-white"
                            )
                            ui.button("🧪 Run Tests", on_click=self._run_tests).classes(
                                "bg-purple-500 text-white"
                            )

                        # AI Summary Section (initially hidden)
                        with ui.column().classes(
                                "w-full h-auto p-4 gap-2 "
                                "border-2 border-white rounded-lg bg-gray-200 hidden"
                        ) as self.ai_summary_container:
                            ui.label("🤖 AI Analysis Summary").classes(
                                "w-full p-2 text-center text-xl font-bold border border-white bg-gray-300"
                            )
                            self.ai_summary_text = ui.textarea(label="Summary").classes(
                                "w-full h-48 border border-white bg-white"
                            )
                            self.ai_summary_text.props("readonly")
                            self.ai_summary_text.set_value(
                                "AI analysis will appear here when processing is complete...")

                        # NEW: AI Chat Section
                        with ui.column().classes(
                                "w-full h-auto p-4 gap-4 mt-4 "
                                "border-2 border-white rounded-lg bg-gray-200"
                        ) as self.chat_container:
                            ui.label("💬 AI Chat - Ask Questions About Your Document").classes(
                                "w-full p-2 text-center text-xl font-bold border border-white bg-gray-300"
                            )

                            # Chat messages area
                            with ui.scroll_area().classes(
                                    "w-full h-64 border border-gray-300 bg-white rounded-lg p-2") as self.chat_messages_container:
                                # Initial message
                                ui.label("💬 Start a conversation about your uploaded document...").classes(
                                    "w-full p-4 text-gray-500 text-center italic")

                            # Chat input area
                            with ui.row().classes("w-full gap-2 items-center mt-2"):
                                self.chat_input = ui.input(
                                    placeholder="Ask a question about your document...").classes("flex-grow")
                                ui.button("Send", on_click=self._send_chat_message).classes(
                                    "bg-green-500 text-white px-4")
                                ui.button("Clear Chat", on_click=self._clear_chat).classes(
                                    "bg-red-500 text-white px-4")

    # endregion -----------------------------------------------------------------------------------

    # region service1 event handlers --------------------------------------------------------------
    async def _health_check(self) -> None:
        """Health check button handler"""
        await self._base_request_handler("get", f"{self.api_gateway_url}/health")

    async def _login_and_store_token(self) -> None:
        """Login button handler"""
        username = self._service1_input1.value
        password = self._service1_input2.value

        if not username or not password:
            ui.notify("Please enter both username and password.")
            return

        data = {"username": username.strip(), "password": password.strip()}

        # For OAuth2 login, we send as form data (not JSON)
        await self._base_request_handler(
            "post", f"{self.api_gateway_url}/auth/login", data=data
        )

    async def _logout_and_delete_token(self) -> None:
        """Logout button handler"""
        if not self._access_token:
            ui.notify("No token found. Please login first.")
            self.service1_textarea1.set_value("No token found. Please login first.")
            return

        headers = {"Authorization": f"Bearer {self._access_token}"}
        await self._base_request_handler(
            "post", f"{self.api_gateway_url}/auth/logout", headers=headers
        )

        self._access_token = None
        ui.notify("Logged out and token deleted.")
        self.service1_textarea1.set_value("Logged out. Token deleted.")

    async def _get_users_list(self) -> None:
        """Get users list button handler"""
        if not self._access_token:
            ui.notify("Please login first to obtain an access token.")
            return

        headers = {"Authorization": f"Bearer {self._access_token}"}
        await self._base_request_handler(
            "get", f"{self.api_gateway_url}/users/list", headers=headers
        )

    async def _get_user_by_id(self) -> None:
        """Get user by ID button handler"""
        if not self._access_token:
            ui.notify("Please login first to obtain an access token.")
            return

        user_id = self._service1_input3.value
        if not user_id:
            ui.notify("Please enter a user ID.")
            return

        headers = {"Authorization": f"Bearer {self._access_token}"}
        await self._base_request_handler(
            "get", f"{self.api_gateway_url}/users/id/{user_id.strip()}", headers=headers
        )

    def _toggle_form(self) -> None:
        """Toggle form visibility"""
        self._form_is_visible = not self._form_is_visible
        if self._form_is_visible:
            self.user_form_container.classes("block").classes(remove="hidden")
        else:
            self.user_form_container.classes("hidden").classes(remove="block")

    async def _create_user(self) -> None:
        """Create user from form"""
        if not self._access_token:
            ui.notify("Please login first to obtain an access token.")
            return

        if (
            not self.user_form_name.value
            or not self.user_form_age.value
            or not self.user_form_city.value
            or not self.user_form_password.value
        ):
            ui.notify("Please fill in all required fields: Name, Age, City, Password.")
            return

        data = {
            "name": self.user_form_name.value,
            "age": int(self.user_form_age.value),
            "city": self.user_form_city.value,
            "email": self.user_form_email.value,
            "password": self.user_form_password.value,
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}
        await self._base_request_handler(
            "post", f"{self.api_gateway_url}/users/create", data=data, headers=headers
        )

        # Clear form fields after user creation
        self.user_form_name.set_value("")
        self.user_form_age.set_value("")
        self.user_form_city.set_value("")
        self.user_form_email.set_value("")
        self.user_form_password.set_value("")

    async def _edit_user(self) -> None:
        """Edit user by ID from form"""
        if not self._access_token:
            ui.notify("Please login first to obtain an access token.")
            return

        user_id = self._service1_input3.value
        if not user_id:
            ui.notify("Please enter a user ID in the ID field above.")
            return

        # Validate required fields
        if (
            not self.user_form_name.value
            or not self.user_form_age.value
            or not self.user_form_city.value
        ):
            ui.notify("Please fill in all required fields: Name, Age, City.")
            return

        data = {
            "name": self.user_form_name.value,
            "age": int(self.user_form_age.value),
            "city": self.user_form_city.value,
            "email": self.user_form_email.value,
            "password": self.user_form_password.value or None,  # Optional for edit
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}
        await self._base_request_handler(
            "put",
            f"{self.api_gateway_url}/users/edit/{user_id}",
            data=data,
            headers=headers,
        )

    async def _delete_user(self) -> None:
        """Delete user by ID from form"""
        if not self._access_token:
            ui.notify("Please login first to obtain an access token.")
            return

        user_id = self._service1_input3.value
        if not user_id:
            ui.notify("Please enter a user ID in the ID field above.")
            return

        headers = {"Authorization": f"Bearer {self._access_token}"}
        await self._base_request_handler(
            "delete", f"{self.api_gateway_url}/users/delete/{user_id}", headers=headers
        )

    async def _on_file_selected(self, file_info) -> None:
        """
        Handle file selection and upload
        :param file_info: the uploaded file info object
        """
        self.uploaded_file_info = file_info

        # Get file size from file-like object
        file_obj = file_info.content
        file_obj.seek(0, 2)  # move to end
        file_size = file_obj.tell()
        file_obj.seek(0)  # reset to start

        ui.notify(f"File selected: {file_info.name} ({file_size} bytes)")

        if not self._access_token:
            ui.notify("Please login first to obtain an access token.")
            return

        file_bytes = file_obj.read()
        file_name = file_info.name
        content_type = getattr(file_info, "type", "application/octet-stream")

        headers = {"Authorization": f"Bearer {self._access_token}"}

        data = aiohttp.FormData()
        data.add_field(
            "file", file_bytes, filename=file_name, content_type=content_type
        )

        self._spinner.set_visibility(True)

        # Show AI summary container immediately with initial message
        self.ai_summary_container.classes("block").classes(remove="hidden")
        self.ai_summary_text.set_value("🔄 Starting document processing pipeline...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.api_gateway_url}/v1/upload", data=data, headers=headers
                ) as response:
                    resp_json = await response.json()
                    self.service1_textarea1.set_value(
                        f"Status: {response.status}\n{json.dumps(resp_json, indent=4)}"
                    )

                    # Start polling if job_id is present
                    job_id = resp_json.get("job_id")
                    if job_id:
                        # Update AI summary to show polling has started
                        self.ai_summary_text.set_value(
                            f"📤 File uploaded successfully!\n\nJob ID: {job_id}\n\nStarting processing pipeline...")

                        # Capture the context BEFORE starting the background task
                        context = ui.context.client
                        asyncio.create_task(self._poll_job_status(job_id, context))

        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            ui.notify(f"Upload failed: {str(e)}")
            self.ai_summary_text.set_value(f"❌ Upload failed: {str(e)}")
        except Exception as e:
            ui.notify(f"Unexpected error during upload: {str(e)}")
            self.ai_summary_text.set_value(f"❌ Unexpected error: {str(e)}")
        finally:
            self._spinner.set_visibility(False)

    # endregion -----------------------------------------------------------------------------------

if __name__ in {"__main__", "__mp_main__"}:
    dashboard = MainApp()
    ui.run(title="AegisAI", port=8080, reload=True)
