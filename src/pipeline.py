"""
Pipeline Orchestrator — AI Pipeline Failure Analyzer
Ties together: ingestion -> embedding -> LLM analysis
Entry point for the full end-to-end pipeline.
"""
 
from src.ingestion.log_parser import parse_log_file, filter_by_severity
from src.embeddings.embedder import LogEmbeddingService
from src.llm.analyzer import FailureAnalyzer
 
 
def run_pipeline(log_file: str, failure_query: str) -> dict:
    """Run the full pipeline from log file to LLM analysis."""
 
    print("\n[STEP 1/4] Parsing log file...")
    entries = parse_log_file(log_file)
    errors = filter_by_severity(entries, "ERROR")
    print(f"  Found {len(entries)} entries, {len(errors)} errors")
 
    print("\n[STEP 2/4] Initializing embedding service...")
    emb_svc = LogEmbeddingService()
 
    print("\n[STEP 3/4] Embedding and storing log entries...")
    added = emb_svc.add_entries(entries)
    print(f"  Stored {added} entries. Total in DB: {emb_svc.count()}")
 
    print("\n[STEP 4/4] Analyzing failure with LLM (RAG)...")
    analyzer = FailureAnalyzer(embedding_service=emb_svc)
    result = analyzer.analyze(failure_query)
 
    return result
 
 
if __name__ == "__main__":
    query = """
    ALERT: Multiple 503 errors on payments API gateway.
    SSL certificate warning in logs. Started 09:14 UTC.
    Customers unable to complete transactions.
    """
 
    result = run_pipeline(
        log_file="data/sample_logs/layer7_failures.log",
        failure_query=query
    )
 
    print("\n" + "="*60)
    print("FINAL ANALYSIS:")
    print(result["analysis"])
