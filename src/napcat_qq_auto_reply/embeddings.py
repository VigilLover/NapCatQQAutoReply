import asyncio
from threading import Lock

from langchain_core.embeddings import Embeddings


class LocalTextEmbeddings(Embeddings):
    def __init__(self, model_name: str, cache_folder: str | None = None):
        self.model_name = model_name
        self.cache_folder = cache_folder
        self._model = None
        self._lock = Lock()

    @property
    def model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    try:
                        self._model = SentenceTransformer(
                            self.model_name,
                            cache_folder=self.cache_folder,
                            local_files_only=True,
                        )
                    except Exception:
                        self._model = SentenceTransformer(
                            self.model_name, cache_folder=self.cache_folder
                        )
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)
