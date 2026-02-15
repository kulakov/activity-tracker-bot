"""RAG knowledge base built on ChromaDB + sentence-transformers."""

import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

import config


class KnowledgeBase:
    def __init__(self):
        self.embedder = SentenceTransformer(config.EMBEDDING_MODEL)
        self.client = chromadb.PersistentClient(path=config.KB_PERSIST_DIR)

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks by paragraphs."""
        chunk_size = config.CHUNK_SIZE
        overlap = config.CHUNK_OVERLAP

        paragraphs = re.split(r"\n\s*\n", text)
        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) > chunk_size and current:
                chunks.append(current.strip())
                # keep tail of previous chunk as overlap
                words = current.split()
                tail_words = max(1, overlap // 5)
                overlap_text = " ".join(words[-tail_words:]) if len(words) > tail_words else ""
                current = overlap_text + "\n\n" + para
            else:
                current = (current + "\n\n" + para) if current else para

        if current.strip():
            chunks.append(current.strip())

        return chunks

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_directory(self, directory: str, collection_name: str) -> int:
        """Ingest all text/markdown files from *directory* into *collection_name*.

        Returns the number of chunks created.
        """
        collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        path = Path(directory)
        files = sorted(
            list(path.glob("**/*.md"))
            + list(path.glob("**/*.txt"))
            + list(path.glob("**/*.rst"))
        )

        if not files:
            return 0

        total = 0
        for file_path in files:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            chunks = self._chunk_text(text)
            if not chunks:
                continue

            embeddings = self.embedder.encode(
                [f"passage: {c}" for c in chunks],
                normalize_embeddings=True,
            ).tolist()

            ids = [f"{file_path.stem}_{total + i}" for i in range(len(chunks))]
            metadatas = [
                {"source": str(file_path.relative_to(path)), "chunk_index": i}
                for i in range(len(chunks))
            ]

            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
            )
            total += len(chunks)

        return total

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, collection_name: str, top_k: int | None = None) -> list[dict]:
        """Return the *top_k* most relevant chunks for *query*."""
        top_k = top_k or config.TOP_K_RESULTS

        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            return []

        query_emb = self.embedder.encode(
            [f"query: {query}"],
            normalize_embeddings=True,
        ).tolist()

        results = collection.query(query_embeddings=query_emb, n_results=top_k)

        out: list[dict] = []
        for i in range(len(results["ids"][0])):
            out.append(
                {
                    "text": results["documents"][0][i],
                    "source": results["metadatas"][0][i].get("source", "?"),
                    "distance": (
                        results["distances"][0][i] if results.get("distances") else None
                    ),
                }
            )
        return out

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def list_collections(self) -> list[str]:
        return [c.name for c in self.client.list_collections()]

    def delete_collection(self, name: str):
        self.client.delete_collection(name)

    def collection_count(self, name: str) -> int:
        try:
            return self.client.get_collection(name).count()
        except Exception:
            return 0
