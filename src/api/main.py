"""
REST API — AI Pipeline Failure Analyzer
Exposes the pipeline as HTTP endpoints.
Auto-generates Swagger docs at /docs
"""
 
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn
 
from src.ingestion.log_parser import parse_log_file
from src.embeddings.embedder import LogEmbeddingService
from src.llm.analyzer import FailureAnalyzer
 
app = FastAPI(
    title="AI Pipeline Failure Analyzer",
    description="RAG-powered root cause analysis for enterprise API gateway and CI/CD failures",
    version="0.1.0",
)
 
# Initialize services once at startup (not on every request)
emb_svc = LogEmbeddingService()
analyzer = FailureAnalyzer(embedding_service=emb_svc)
 
 
class AnalyzeRequest(BaseModel):
    failure_description: str
    n_similar_logs: Optional[int] = 5
 
 
class AnalyzeResponse(BaseModel):
    analysis: str
    similar_logs_found: int
    model_used: str
    tokens_used: dict
 
 
@app.get("/health")
def health_check():
    """Health check endpoint — used by load balancers and monitoring."""
    return {"status": "healthy", "log_entries_in_db": emb_svc.count()}
 
 
@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze_failure(request: AnalyzeRequest):
    """
    Analyze a pipeline failure and return root cause analysis.
    Retrieves similar past failures from vector DB and uses LLM for analysis.
    """
    if not request.failure_description.strip():
        raise HTTPException(status_code=400, detail="failure_description cannot be empty")
 
    result = analyzer.analyze(
        failure_description=request.failure_description,
        n_similar=request.n_similar_logs,
    )
 
    return AnalyzeResponse(
        analysis=result["analysis"],
        similar_logs_found=len(result["retrieved_logs"]),
        model_used=result["model_used"],
        tokens_used={"input": result["input_tokens"], "output": result["output_tokens"]},
    )
 
 
@app.post("/api/v1/ingest")
def ingest_logs(log_file_path: str = "data/sample_logs/layer7_failures.log"):
    """Ingest a log file into the vector database."""
    entries = parse_log_file(log_file_path)
    added = emb_svc.add_entries(entries)
    return {"message": f"Ingested {added} entries", "total_in_db": emb_svc.count()}
 
 
if __name__ == "__main__":
    # Seed the DB on startup
    if emb_svc.count() == 0:
        entries = parse_log_file("data/sample_logs/layer7_failures.log")
        emb_svc.add_entries(entries)
    uvicorn.run(app, host="0.0.0.0", port=8000)
