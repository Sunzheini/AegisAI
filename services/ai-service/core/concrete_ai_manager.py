"""
Concrete AI implementation
"""

import os
import sys
import subprocess
from pathlib import Path

import tempfile
from dotenv import load_dotenv
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.history_aware_retriever import (
    create_history_aware_retriever,
)
from langchain_classic.chains.retrieval import create_retrieval_chain
from pinecone import Pinecone
from langsmith import Client
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore

from shared_lib.contracts.job_schemas import WorkflowGraphState

from support.callback_handler import CustomCallbackHandler
from support.useful_functions import split_document

load_dotenv()

pinecone_api_key = os.getenv("PINECONE_API_KEY")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
index_name = os.getenv("INDEX_NAME")
index2_name = os.getenv("INDEX_NAME")


class ConcreteAIManager:
    """Concrete AI Manager for handling AI-related operations."""

    base_dir = Path(__file__).resolve().parent.parent
    s3_client = None

    @staticmethod
    def split_txt_into_chunks(state: WorkflowGraphState) -> list:
        """
        Test splitting a txt document into text chunks.
        """
        # Check if we have extracted text in metadata
        if state.get("metadata") and state["metadata"].get("text_extraction"):

            # Get the path to the extracted text file
            path_to_file = state["metadata"]["text_extraction"].get("text_file_path")

            if path_to_file:
                # Handle S3 paths - download temporarily
                if path_to_file.startswith("s3://"):
                    print(f"[AI Service] S3 path detected: {path_to_file}")

                    try:
                        # Parse S3 path
                        bucket_key = path_to_file[5:]  # Remove 's3://'
                        bucket_name, key = bucket_key.split("/", 1)

                        # Download to temp file
                        temp_dir = tempfile.gettempdir()
                        local_path = os.path.join(temp_dir, os.path.basename(key))

                        print(f"[AI Service] Downloading from S3: {bucket_name}/{key}")
                        ConcreteAIManager.s3_client.download_file(
                            bucket_name, key, local_path
                        )

                        # Split the downloaded file
                        texts = split_document(".txt", local_path)

                        # Clean up temp file
                        os.remove(local_path)
                        print(f"[AI Service] Cleaned up temp file: {local_path}")

                        return texts

                    except Exception as e:
                        print(f"[AI Service] Failed to process S3 file: {e}")
                        return []

                # Handle local files (existing logic)
                elif os.path.exists(path_to_file):
                    print(f"[AI Service] Local file found: {path_to_file}")
                    texts = split_document(".txt", path_to_file)
                    return texts
                else:
                    print(f"[AI Service] File not found: {path_to_file}")

        return []

    @staticmethod
    def ingest_txt_into_cloud_vector_store(texts: list) -> None:
        """
        Test ingesting txt content into a vector store and querying it.
        This is an integration test that requires OpenAI API access.
        """
        # 0
        embeddings = OpenAIEmbeddings()

        # 2
        pinecone_index_name = index_name
        vectorstore = PineconeVectorStore.from_documents(
            texts,
            embeddings,
            index_name=pinecone_index_name,
            pinecone_api_key=pinecone_api_key,
        )

    @staticmethod
    def get_retrieval_chain():
        """Create a document retrieval chain with chat history similar to the test cases."""
        # 0
        embeddings = OpenAIEmbeddings()

        # 2
        pinecone_index_name = index_name
        vectorstore = PineconeVectorStore(
            index_name=pinecone_index_name,
            embedding=embeddings,
            pinecone_api_key=pinecone_api_key,
        )

        # 3
        client = Client(api_key=LANGSMITH_API_KEY)
        retrieval_qa_chat_prompt = client.pull_prompt(
            "langchain-ai/retrieval-qa-chat", include_model=True
        )
        rephrase_prompt = client.pull_prompt(
            "langchain-ai/chat-langchain-rephrase", include_model=True
        )

        # 4
        llm = ChatOpenAI(
            model_name="gpt-4.1-mini",
            temperature=0,
            callbacks=[CustomCallbackHandler()],
        )

        # 5
        history_aware_retriever = create_history_aware_retriever(
            llm=llm, retriever=vectorstore.as_retriever(), prompt=rephrase_prompt
        )

        combine_docs_chain = create_stuff_documents_chain(
            llm=llm, prompt=retrieval_qa_chat_prompt
        )

        chain = create_retrieval_chain(
            retriever=history_aware_retriever, combine_docs_chain=combine_docs_chain
        )

        return chain

    @staticmethod
    def retrieve_from_txt_in_cloud(query, chat_history=None):
        """Retrieve information from ingested txt content in vector store."""
        if chat_history is None:
            chat_history = []

        # 0 - 5
        chain = ConcreteAIManager.get_retrieval_chain()

        # 6
        responses = {}
        for key, prompt in query.items():
            query = prompt
            print(f"before request {key}: {query}")
            response = chain.invoke(
                input={"input": query, "chat_history": chat_history}
            )

            # Store response for later assertions
            responses[key] = response["answer"]

            # ------------------------------------------------------------------------------
            chat_history.append(("human", query))
            chat_history.append(("ai", response["answer"]))

            print(f'Response for {key}: {response["answer"][:100]}...')
            print("-" * 10)

        return {"responses": responses, "chat_history": chat_history}

    @staticmethod
    async def cleanup_data():
        """Cleanup Pinecone indexes"""
        all_indexes_in_pinecone = [index_name, index2_name]
        try:
            if not pinecone_api_key:
                return {"error": "Missing Pinecone API key"}

            if not all_indexes_in_pinecone:
                return {"error": "No index names configured"}

            pc = Pinecone(api_key=pinecone_api_key)

            # Get existing indexes
            existing_indexes = []
            try:
                existing_indexes = [idx.name for idx in pc.list_indexes()]
            except Exception as e:
                return {"error": f"Failed to list indexes: {str(e)}"}

            cleanup_results = {}
            for idx in all_indexes_in_pinecone:
                if idx in existing_indexes:
                    try:
                        index = pc.Index(idx)
                        stats = index.describe_index_stats()
                        total_vectors = stats.get("total_vector_count", 0)

                        if total_vectors > 0:
                            index.delete(delete_all=True)
                            cleanup_results[idx] = f"Cleaned up {total_vectors} vectors"
                            print(
                                f"[Cleanup] Cleaned up {total_vectors} vectors from {idx}"
                            )
                        else:
                            cleanup_results[idx] = "No vectors to clean up"
                            print(f"[Cleanup] No vectors to clean up in {idx}")
                    except Exception as e:
                        cleanup_results[idx] = f"Error cleaning index: {str(e)}"
                else:
                    cleanup_results[idx] = "Index does not exist"
                    print(f"[Cleanup] Index {idx} does not exist")

            return {
                "success": True,
                "results": cleanup_results,
                "message": "Cleanup operation completed",
            }

        except Exception as e:
            print(f"[Cleanup] Error: {e}")
            return {"error": str(e)}

    @staticmethod
    async def run_tests(request: dict = None):
        """Run tests programmatically"""
        try:
            test_pattern = request.get("test_pattern") if request else None

            cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
            if test_pattern:
                cmd.extend(["-k", test_pattern])
            else:
                cmd.append("tests/")

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "stdout": "", "stderr": ""}
