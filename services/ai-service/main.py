"""
AI Service
------------------
Standalone service that executes tasks using LLM calls.
Uses RedisManager for consistent connection management.
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from shared_lib.contracts.job_schemas import WorkflowGraphState
from shared_lib.needs.INeedRedisManager import INeedRedisManagerInterface
from shared_lib.needs.ResolveNeedsManager import ResolveNeedsManager
from shared_lib.redis_management.redis_manager import RedisManager
from shared_lib.custom_middleware.error_middleware import ErrorMiddleware
from shared_lib.custom_middleware.logging_middleware import EnhancedLoggingMiddleware
from shared_lib.logging_management.logging_manager import LoggingManager


# Configuration
AI_QUEUE = os.getenv("AI_QUEUE", "ai_queue")
AI_CALLBACK_QUEUE = os.getenv("AI_CALLBACK_QUEUE", "ai_callback_queue")

# Upload/raw storage location constant (configurable)
UPLOAD_DIR = Path(os.getenv("PROCESSED_DIR", "storage/processed")).resolve()

# ai processing constraints
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", 500000))  # 10k characters default

logger = LoggingManager.setup_logging(
    service_name="ai-service",
    log_file_path="logs/ai_service.log",
    log_level=logging.INFO,
)


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager to start/stop Redis listener."""
    logger.info("Starting AI Service...")

    # Create RedisManager
    redis_manager = RedisManager()

    # Create ai service and inject RedisManager
    ai_service = AIService()
    ResolveNeedsManager.resolve_needs(ai_service)

    # Store in app.state
    app.state.extract_text_service = ai_service
    app.state.redis_manager = redis_manager

    print("[AIService] Starting Redis listener...")
    logger.info("Starting Redis listener...")
    task = asyncio.create_task(redis_listener(ai_service))
    yield
    print("[AIService] Shutting down Redis listener.")
    logger.info("Shutting down Redis listener.")
    task.cancel()
    await app.state.redis_manager.close()


app = FastAPI(title="AI Service", lifespan=lifespan)
app.add_middleware(ErrorMiddleware)
app.add_middleware(EnhancedLoggingMiddleware, service_name="ai-service")


class AIService(INeedRedisManagerInterface):
    """Handles ai processing tasks using shared RedisManager."""

    def __init__(self):
        self.logger = logging.getLogger("ai-service")
        self.MAX_TEXT_LENGTH = MAX_TEXT_LENGTH

        # Instance-level configuration

    async def process_ai_task(self, task_data: dict) -> dict:
        """Process ai task using shared Redis connection."""
        try:
            state = WorkflowGraphState(**task_data)
            result_state = await self._process_ai_worker(state)
            return dict(result_state)
        except Exception as e:
            self.logger.error(f"AI processing failed: {e}")
            return {
                "job_id": task_data.get("job_id"),
                "status": "failed",
                "step": "ai_processing_failed",
                "metadata": {"errors": [str(e)]},
                "updated_at": self._current_timestamp(),
            }

    # region AI Processing Methods
    @staticmethod
    async def _load_text_for_processing(state: WorkflowGraphState) -> str:
        """Load text content for AI processing from extracted text or file."""
        text_content = ""

        # Check if we have extracted text in metadata
        if state.get("metadata") and state["metadata"].get("text_extraction"):
            # First try to load from the saved text file (full content)
            text_file_path = state["metadata"]["text_extraction"].get("text_file_path")
            if text_file_path and os.path.exists(text_file_path):
                try:
                    with open(text_file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                        print(f"[AI Service] Loaded full text from file: {len(text_content)} characters")
                except Exception as e:
                    print(f"[AI Service] Failed to read text file: {str(e)}")
                    # Fall back to extracted text in metadata
                    text_content = state["metadata"]["text_extraction"].get("extracted_text", "")

            # If still no content, use preview
            if not text_content and state["metadata"]["text_extraction"].get("text_preview"):
                text_content = state["metadata"]["text_extraction"]["text_preview"]
                print(f"[AI Service] Using text preview: {len(text_content)} characters")

        return text_content

    @staticmethod
    async def _generate_document_summary(text: str, job_id: str) -> dict:
        """Generate a document summary using dummy AI logic."""
        # Simulate AI processing delay
        await asyncio.sleep(0.3)

        # Dummy AI analysis - in real scenario, this would call an LLM API
        word_count = len(text.split())
        sentence_count = len([s for s in text.split('.') if s.strip()])

        # Simple keyword extraction (dummy implementation)
        words = text.lower().split()
        common_words = ['the', 'and', 'is', 'in', 'to', 'of', 'a', 'for']
        keywords = [word for word in words if word not in common_words and len(word) > 4]
        top_keywords = list(set(keywords))[:10]  # Get top 10 unique keywords

        # Generate summary based on content
        if word_count > 500:
            summary_type = "detailed_document"
            summary_length = "long"
        elif word_count > 100:
            summary_type = "standard_document"
            summary_length = "medium"
        else:
            summary_type = "brief_note"
            summary_length = "short"

        # Create dummy summary
        summary = f"This is a {summary_length} {summary_type} containing approximately {word_count} words. "
        summary += f"Key topics include: {', '.join(top_keywords[:3]) if top_keywords else 'general content'}."

        return {
            "summary": summary,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "estimated_reading_time_minutes": max(1, word_count // 200),  # 200 wpm
            "key_topics": top_keywords[:5],
            "content_type": summary_type,
            "readability_score": min(100, max(30, 80 - (word_count // 100))),  # Dummy score
        }

    @staticmethod
    async def _analyze_sentiment_and_tone(text: str) -> dict:
        """Analyze sentiment and tone using dummy AI logic."""
        await asyncio.sleep(0.2)

        # Dummy sentiment analysis
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'positive', 'success']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'negative', 'failure', 'problem']

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            sentiment = "positive"
            confidence = min(100, positive_count * 15)
        elif negative_count > positive_count:
            sentiment = "negative"
            confidence = min(100, negative_count * 15)
        else:
            sentiment = "neutral"
            confidence = 50

        # Dummy tone analysis
        formal_indicators = ['however', 'therefore', 'furthermore', 'additionally']
        casual_indicators = ['hey', 'hello', 'thanks', 'please', '!']

        formal_score = sum(1 for word in formal_indicators if word in text_lower)
        casual_score = sum(1 for word in casual_indicators if word in text_lower)

        if formal_score > casual_score:
            tone = "formal"
        elif casual_score > formal_score:
            tone = "casual"
        else:
            tone = "neutral"

        return {
            "sentiment": sentiment,
            "sentiment_confidence": confidence,
            "tone": tone,
            "positive_indicators": positive_count,
            "negative_indicators": negative_count,
        }

    @staticmethod
    async def _extract_entities_and_topics(text: str) -> dict:
        """Extract entities and topics using dummy AI logic."""
        await asyncio.sleep(0.25)

        # Dummy entity extraction
        entities = {
            "people": [],
            "organizations": [],
            "locations": [],
            "dates": [],
            "topics": []
        }

        # Simple pattern matching for dummy entities
        words = text.split()
        for i, word in enumerate(words):
            if word.istitle() and len(word) > 2:
                # Simple heuristic for proper nouns
                if i > 0 and words[i - 1] in ['Mr.', 'Ms.', 'Dr.']:
                    entities["people"].append(word)
                elif word.endswith(('Inc.', 'Ltd.', 'Corp.')):
                    entities["organizations"].append(word)
                elif word in ['Paris', 'London', 'New York', 'Berlin']:
                    entities["locations"].append(word)

        # Remove duplicates
        for key in entities:
            entities[key] = list(set(entities[key]))

        # Dummy topic modeling
        technical_terms = ['algorithm', 'system', 'data', 'process', 'technology', 'development']
        business_terms = ['business', 'market', 'strategy', 'growth', 'revenue', 'customer']

        tech_count = sum(1 for term in technical_terms if term in text.lower())
        business_count = sum(1 for term in business_terms if term in text.lower())

        if tech_count > business_count:
            entities["topics"] = ["technology", "software", "systems"]
        elif business_count > tech_count:
            entities["topics"] = ["business", "strategy", "market"]
        else:
            entities["topics"] = ["general", "information"]

        return entities

    @staticmethod
    async def _generate_ai_insights(summary: dict, sentiment: dict, entities: dict) -> dict:
        """Generate comprehensive AI insights from all analyses."""
        insights = []

        # Generate insights based on analysis results
        if sentiment["sentiment"] == "positive":
            insights.append("The document has a generally positive tone")
        elif sentiment["sentiment"] == "negative":
            insights.append("The document contains negative sentiment that may require attention")

        if summary["word_count"] > 1000:
            insights.append("This is a comprehensive document requiring detailed review")
        elif summary["word_count"] < 200:
            insights.append("This is a brief document suitable for quick reading")

        if entities["people"]:
            insights.append(f"Document references {len(entities['people'])} key people")

        if "technology" in entities["topics"]:
            insights.append("Content focuses on technical subjects")

        return {
            "insights": insights,
            "overall_complexity": "high" if summary["word_count"] > 800 else "medium" if summary[
                                                                                             "word_count"] > 300 else "low",
            "recommended_actions": ["Review key topics", "Consider sentiment in response"] if insights else [
                "Standard processing complete"],
        }
    # endregion

    async def _process_ai_worker(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """
        Processing with AI.
        Updates the job state with the results of the ai processing.
        Args:
            state (WorkflowGraphState): The job state dictionary containing file metadata and path.
        Returns:
            WorkflowGraphState: Updated job state after ai processing.

        Look like: {
        'job_id': '51be2080-e3e0-4e2b-962d-8d5f2e81c127',
        'file_path': 'D:\\Study\\Projects\\Github\\AegisAI\\shared-storage\\raw\\51be2080-e3e0-4e2b-962d-8d5f2e81c127_P8052AH.pdf',
        'content_type': 'application/pdf',
        'checksum_sha256': '4ee5bec8416491b15f6ff615059e22eb30d0b5662167ce0e972bb84aa1648016',
        'submitted_by': 'Bob',
        'status': 'success',
        'created_at': '2025-10-28T09:40:24.192919+00:00',
        'updated_at': '2025-10-28T09:40:29.095009+00:00',
        'step': 'ai_processing_done',
        'branch': 'pdf_branch',
        'metadata': {
            'validation': 'passed',
            'file_size': 780647,
            'file_extension': '.pdf',
            'created_timestamp':
            '2025-10-28T09:40:24.179919+00:00',
            'modified_timestamp': '2025-10-28T09:40:24.184920+00:00',
            'magic_number_verified': True,
            'page_count': 21,
            'is_encrypted': False,
            'document_info': {
                'ModDate': "D:20060423164721+09'00'",
                'CreationDate': 'D:19970617164339Z',
                'Title': 'DATASHEET SEARCH SITE | WWW.ALLDATASHEET.COM',
                'Creator': 'Acrobat Capture 1.0',
                'Author': 'Provided By ALLDATASHEET.COM(FREE DATASHEET DOWNLOAD SITE)',
                'Keywords': 'PDF, DATASHEET, PDF DATASHEET, IC, CHIP, SEMICONDUCTOR, TRANSISTOR, ELECTRONIC COMPONENT, ISO COMPONENT, ALLDATASHEET, DATABOOK, CATALOG, ARCHIVE',
                'Subject': 'DATASHEET SEARCH, DATABOOK, COMPONENT, FREE DOWNLOAD SITE',
                'Producer': 'Acrobat PDFWriter 2.01 for Windows'},
            'extracting_metadata': 'passed',
            'text_extraction': {
                'success': True,
                'extracted_character_count': 33608,
                'total_pages': 21,
                'pages_with_text': 21,
                'text_file_path': 'D:\\Study\\Projects\\Github\\AegisAI\\shared-storage\\processed\\51be2080-e3e0-4e2b-962d-8d5f2e81c127_extracted_text.txt',
                'file_stats': {
                    'saved_at': '2025-10-28T09:40:27.844876+00:00',
                    'file_size_bytes': 35496,
                    'character_count': 33608,
                    'file_path': 'D:\\Study\\Projects\\Github\\AegisAI\\shared-storage\\processed\\51be2080-e3e0-4e2b-962d-8d5f2e81c127_extracted_text.txt'},
                'content_analysis': {
                    'word_count': 4334,
                    'paragraph_count': 21,
                    'avg_words_per_page': 0,
                    'language_indicators': {},
                    'content_categories': ['technical_document', 'datasheet']},
                'extraction_time': '2025-10-28T09:40:27.844876+00:00',
                'text_preview': '--- Page 1 ---\nnmu @\nMCS@51\n8-BIT CONTROL-ORIENTED MICROCONTROLLERS\nCommercial/Express\n8031AH18051AH18051AHP\n8032N+18052N-I\n8751W8751H-8\n8751BW8752BI-I\nn HighPerformance HMOSProcess n BooleanProcessor\nn Internal Timers/Event Counters n Bit-Addressable RAM\nn 2-Level interrupt Priority Structure n ProgrammableFullDuplexSerial\nChannel\nn 32 1/0 Lines(Four 8-Bit Ports)\nn 111Instructions(64 Single-Cycle)\nn 64K External ProgramMemory Space\n64K External Data Memory Space\nn Security Feature Protects EPRO...'},
                'extract_text': 'passed',
                'ai_processing': {
                    'document_summary': {
                        'summary': 'This is a long detailed_document containing approximately 4334 words. Key topics include: 30pf+10, cycle, abyteofthe.',
                        'word_count': 4334,
                        'sentence_count': 430,
                        'estimated_reading_time_minutes': 21,
                        'key_topics': ['30pf+10', 'cycle', 'abyteofthe', 'frominternalmemory,eais', 'units'],
                        'content_type': 'detailed_document', 'readability_score': 37},
                    'sentiment_analysis': {
                        'sentiment': 'positive',
                        'sentiment_confidence': 15,
                        'tone': 'casual',
                        'positive_indicators': 1,
                        'negative_indicators': 0},
                    'entity_extraction': {
                        'people': [],
                        'organizations': [],
                        'locations': [],
                        'dates': [],
                        'topics': ['technology', 'software', 'systems']},
                    'ai_insights': {
                        'insights': ['The document has a generally positive tone', 'This is a comprehensive document requiring detailed review', 'Content focuses on technical subjects'],
                        'overall_complexity': 'high',
                        'recommended_actions': ['Review key topics', 'Consider sentiment in response']},
                    'processing_timestamp': '2025-10-28T09:40:29.095009+00:00',
                    'model_used': 'dummy_ai_v1.0'},
                'ai_processing_status': 'completed'}}
        """
        print(f"[Worker:ai_processing_file] Job {state['job_id']} ai processing...")
        await asyncio.sleep(0.5)
        errors = []

        # -------------------------------------------------------------------------------
        # The real AI processing!
        # -------------------------------------------------------------------------------
        ai_results = {}

        try:
            # Load text content for processing
            text_content = await self._load_text_for_processing(state)

            if not text_content:
                errors.append("No text content available for AI processing")
            else:
                # Apply length limit
                if len(text_content) > self.MAX_TEXT_LENGTH:
                    text_content = text_content[:self.MAX_TEXT_LENGTH]
                    ai_results["text_truncated"] = True
                    ai_results["original_length"] = len(text_content)

                # Perform various AI analyses
                summary = await self._generate_document_summary(text_content, state["job_id"])
                sentiment = await self._analyze_sentiment_and_tone(text_content)
                entities = await self._extract_entities_and_topics(text_content)
                insights = await self._generate_ai_insights(summary, sentiment, entities)

                # Compile all AI results
                ai_results.update({
                    "document_summary": summary,
                    "sentiment_analysis": sentiment,
                    "entity_extraction": entities,
                    "ai_insights": insights,
                    "processing_timestamp": datetime.now(timezone.utc).isoformat(),
                    "model_used": "dummy_ai_v1.0",  # In real scenario, this would be the actual model
                })

                print(30 * '-')
                print(ai_results)
                print(30 * '-')

        except Exception as e:
            errors.append(f"AI processing failed: {str(e)}")

        # -------------------------------------------------------------------------------
        if "metadata" not in state or state["metadata"] is None:
            state["metadata"] = {}

        if errors:
            state["status"] = "failed"
            state["step"] = "ai_processing_failed"
            state["metadata"]["errors"] = errors

            # Include any partial AI results if available
            if ai_results:
                state["metadata"]["ai_processing"] = {
                    "success": False,
                    "errors": errors,
                    "partial_results": ai_results
                }

        else:
            state["status"] = "success"
            state["step"] = "ai_processing_done"
            state["metadata"]["ai_processing"] = ai_results  # Add AI results to existing metadata
            state["metadata"]["ai_processing_status"] = "completed"  # Add success flag

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        print(
            f"[Worker:ai_processing] Job {state['job_id']} AI processing done. State: {state}"
        )
        return state

    @staticmethod
    def _current_timestamp():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai_processing"}


# ----------------------------------------------------------------------------------------------
# Redis listener to subscribe to validation tasks
# ----------------------------------------------------------------------------------------------
async def redis_listener(ai_service: AIService):
    """Redis listener using shared RedisManager."""
    redis_client = await ai_service.redis_manager.get_redis_client()
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(AI_QUEUE)
        print(f"[AIService] Listening on '{AI_QUEUE}'...")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    task = json.loads(message["data"])
                    job_id = task.get("job_id", "unknown")
                    print(f"[AIService] Processing job: {job_id}")

                    result = await ai_service.process_ai_task(task)

                    # Use shared Redis connection to publish result
                    await redis_client.publish(
                        AI_CALLBACK_QUEUE,
                        json.dumps({"job_id": job_id, "result": result}),
                    )
                    print(f"[AIService] Published result for: {job_id}")

                except Exception as e:
                    print(f"[AIService] Error: {e}")

    except asyncio.CancelledError:
        print("[AIService] Listener cancelled")
    finally:
        await pubsub.unsubscribe(AI_QUEUE)
        await pubsub.close()
