import chromadb
from app.config.settings import settings

class ChromaClient:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_path)

    def get_collection(self, name: str):
        return self.client.get_or_create_collection(name=name)
