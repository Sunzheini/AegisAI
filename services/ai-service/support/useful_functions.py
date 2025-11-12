from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader


def split_document(file_type, file_path) -> list[Document] | None:
    """
    Loads and splits the file (.pdf or .txt) once.
    """
    loader = None
    if file_type == '.pdf':
        loader = PyPDFLoader(file_path)
    elif file_type == '.txt':
        loader = TextLoader(file_path, encoding='utf8')

    documents = loader.load()
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=30, separator="\n")
    texts = text_splitter.split_documents(documents)

    print(f"Document has been split into {len(texts)} chunks.")
    return texts
