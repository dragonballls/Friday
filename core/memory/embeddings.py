import os
import pickle
import re
import time

from core.logger import info

MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "memory_store")
EMBEDDINGS_PATH = os.path.join(MEMORY_DIR, "embeddings.pkl")
os.makedirs(MEMORY_DIR, exist_ok=True)

_WORD_RE = re.compile(r"\w+")


class EmbeddingEntry:
    def __init__(self, text: str, metadata: dict | None = None):
        self.text = text
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.id = self.metadata.get("id", str(time.time()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text[:300],
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class TfidfEngine:
    """Lightweight local text retrieval with no neural/model runtime."""

    def __init__(self):
        self._entries: list[EmbeddingEntry] = []
        self._vectorizer = None
        self._matrix = None
        self._dirty = False
        self._needs_rebuild = False

    def store(self, text: str, metadata: dict | None = None) -> dict:
        entry = EmbeddingEntry(text, metadata)
        self._entries.append(entry)
        self._dirty = True
        self._needs_rebuild = True
        return {"id": entry.id, "text": text[:80], "success": True}

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._entries:
            return []
        if self._needs_rebuild:
            self._ensure_index()
            self._needs_rebuild = False
        if self._vectorizer is None or self._matrix is None:
            return []
        try:
            query_vec = self._vectorizer.transform([query])
            from sklearn.metrics.pairwise import cosine_similarity

            scores = cosine_similarity(query_vec, self._matrix)[0]
            scored = [(float(scores[i]), self._entries[i]) for i in range(len(self._entries))]
            scored.sort(key=lambda x: -x[0])
            return [
                {
                    "id": entry.id,
                    "text": entry.text[:300],
                    "score": round(score, 4),
                    "metadata": entry.metadata,
                    "created_at": entry.created_at,
                }
                for score, entry in scored[:top_k]
                if score >= 0.05
            ]
        except Exception as e:
            info(f"Embedding search error: {e}")
            return []

    def search_by_text(self, query: str, top_k: int = 5) -> list[dict]:
        return self.search(query, top_k)

    def delete(self, entry_id: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        if len(self._entries) < before:
            self._dirty = True
            self._needs_rebuild = True
            return True
        return False

    def list_all(self, limit: int = 50) -> list[dict]:
        entries = sorted(self._entries, key=lambda e: e.created_at, reverse=True)
        return [e.to_dict() for e in entries[:limit]]

    def clear(self):
        self._entries.clear()
        self._vectorizer = None
        self._matrix = None
        self._dirty = True
        self._needs_rebuild = False

    def count(self) -> int:
        return len(self._entries)

    def get_entries(self) -> list[EmbeddingEntry]:
        return list(self._entries)

    def _ensure_index(self):
        if self._vectorizer is not None and not self._dirty:
            return
        if not self._entries:
            self._vectorizer = None
            self._matrix = None
            return
        from sklearn.feature_extraction.text import TfidfVectorizer

        texts = [e.text for e in self._entries]
        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            token_pattern=r"(?u)\b\w+\b",
        )
        self._matrix = self._vectorizer.fit_transform(texts)
        self._dirty = False

    def persist(self):
        try:
            data = [(e.text, e.metadata, e.created_at, e.id) for e in self._entries]
            with open(EMBEDDINGS_PATH, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            info(f"Failed to save embeddings: {e}")

    def restore(self):
        if not os.path.exists(EMBEDDINGS_PATH):
            return
        try:
            with open(EMBEDDINGS_PATH, "rb") as f:
                data = pickle.load(f)
            if not isinstance(data, list):
                return
            for text, metadata, created_at, eid in data:
                entry = EmbeddingEntry(text, metadata)
                entry.created_at = created_at
                entry.id = eid
                self._entries.append(entry)
            self._dirty = True
            self._needs_rebuild = True
            info(f"Restored {len(self._entries)} text-index entries")
        except Exception as e:
            info(f"Failed to restore embeddings: {e}")


class EmbeddingEngine:
    """Retrieval engine that deliberately contains no neural embedding model."""

    def __init__(self):
        self._engine = TfidfEngine()
        self._engine.restore()
        info("Using TF-IDF text retrieval; no local AI model is loaded")

    def store(self, text: str, metadata: dict | None = None) -> dict:
        return self._engine.store(text, metadata)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        return self._engine.search(query, top_k)

    def delete(self, entry_id: str) -> bool:
        return self._engine.delete(entry_id)

    def list_all(self, limit: int = 50) -> list[dict]:
        return self._engine.list_all(limit)

    def clear(self):
        self._engine.clear()

    def count(self) -> int:
        return self._engine.count()

    def get_entries(self) -> list[EmbeddingEntry]:
        return self._engine.get_entries()

    def persist(self):
        self._engine.persist()
        self._engine._dirty = False

    def is_dirty(self) -> bool:
        return self._engine._dirty

    def get_engine_type(self) -> str:
        return "tfidf"
