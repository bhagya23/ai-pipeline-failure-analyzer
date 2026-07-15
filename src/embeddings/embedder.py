"""
Embedding Service — AI Pipeline Failure Analyzer
Responsibility: Convert LogEntry objects into vector embeddings and store/retrieve them via ChromaDB.
Uses sentence-transformers for free local embeddings (no API key required in dev).
"""
 
import os
import sys
import uuid
from typing import List, Dict, Any
from dataclasses import asdict
 
import chromadb
from chromadb.utils import embedding_functions
 
# Import our LogEntry dataclass from Day 2.
# When executing this module directly, ensure the src package root is on sys.path.
try:
    from src.ingestion.log_parser import LogEntry
except ModuleNotFoundError:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from ingestion.log_parser import LogEntry
 
 
class LogEmbeddingService:
    """
    Manages the ChromaDB collection for log entries.
    Key operations: add entries, search by similarity, get by ID.
    """
 
    COLLECTION_NAME = "pipeline_failures"
 
    def __init__(self, persist_dir: str = "./data/chroma_db"):
        """
        Initialize ChromaDB client and collection.
        persist_dir: where ChromaDB saves its data to disk.
        Falls back to a simple hash-based embedding if Torch is blocked by OS policy.
        """
        # Create the persist directory if it does not exist
        os.makedirs(persist_dir, exist_ok=True)
 
        # Initialize ChromaDB with local persistence
        self.client = chromadb.PersistentClient(path=persist_dir)
 
        # Try to use a free local embedding model; fall back if blocked by OS policy
        self.embedding_fn = None
        try:
            # "all-MiniLM-L6-v2" is fast, small, and good enough for log similarity
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            print("[INFO] Using SentenceTransformer embeddings (all-MiniLM-L6-v2)")
        except (OSError, ImportError) as e:
            if isinstance(e, OSError) and "WinError 4551" in str(e):
                print("[WARN] Torch blocked by OS policy (WinError 4551). Falling back to default embedding.")
            else:
                print(f"[WARN] Embedding model failed ({type(e).__name__}). Falling back to default embedding.")
            # ChromaDB will use its default embedding function when None is passed
            self.embedding_fn = None
 
        # Get or create our collection
        if self.embedding_fn:
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"}   # cosine similarity for semantic search
            )
        else:
            # Fallback: use default embedding (usually based on Chroma's built-in)
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        print(f"[INFO] ChromaDB initialized. Collection: {self.COLLECTION_NAME}. Items: {self.collection.count()}")
 
    def add_entries(self, entries: List[LogEntry]) -> int:
        """
        Add a list of LogEntry objects to ChromaDB.
        Skips entries that are already stored (idempotent).
        Returns the number of new entries added.
        """
        documents = []       # the text to embed
        metadatas = []       # structured metadata stored alongside
        ids = []             # unique ID for each entry
 
        for entry in entries:
            # Create a unique ID from timestamp + source + first 30 chars of message
            entry_id = str(uuid.uuid5(uuid.NAMESPACE_DNS,
                f"{entry.timestamp}_{entry.source}_{entry.message[:30]}"))
 
            # The text we embed is a combination of source + message
            # This gives the model context about WHERE the failure occurred
            document_text = f"[{entry.source}] {entry.message}"
 
            metadata = {
                "timestamp": entry.timestamp,
                "severity": entry.severity,
                "source": entry.source,
                "raw_line": entry.raw_line,
            }
 
            documents.append(document_text)
            metadatas.append(metadata)
            ids.append(entry_id)
 
        if not documents:
            return 0
 
        # ChromaDB upsert: adds new, ignores duplicates
        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[INFO] Upserted {len(documents)} entries into ChromaDB")
        return len(documents)
 
    def search_similar(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Given a failure description, find the most semantically similar past log entries.
        Returns a list of dicts with document text, metadata, and similarity distance.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, self.collection.count()),
        )
 
        # Format the results for easy consumption
        formatted = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            formatted.append({
                "text": doc,
                "metadata": meta,
                "similarity_score": round(1 - dist, 4),   # 1 = identical, 0 = unrelated
            })
        return formatted
 
    def count(self) -> int:
        return self.collection.count()
 
 
# ── Smoke test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        from src.ingestion.log_parser import parse_log_file
    except ModuleNotFoundError:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        from ingestion.log_parser import parse_log_file
 
    # Step 1: Load log entries from Day 2
    entries = parse_log_file("data/sample_logs/layer7_failures.log")
    print(f"Loaded {len(entries)} entries")
 
    # Step 2: Initialize embedding service
    svc = LogEmbeddingService()
 
    # Step 3: Embed and store all entries
    added = svc.add_entries(entries)
    print(f"Added {added} entries. Total in DB: {svc.count()}")
 
    # Step 4: Test semantic search
    print("\nSearching for: SSL certificate issues...")
    results = svc.search_similar("SSL certificate expired authentication failure", n_results=3)
    for r in results:
        print(f"  [{r['similarity_score']:.3f}] {r['text'][:80]}")
 
    print("\nSearching for: CI pipeline test failures...")
    results = svc.search_similar("unit test failed pipeline broken", n_results=3)
    for r in results:
        print(f"  [{r['similarity_score']:.3f}] {r['text'][:80]}")
