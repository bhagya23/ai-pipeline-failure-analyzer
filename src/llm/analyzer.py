"""
LLM Analysis Service — AI Pipeline Failure Analyzer
Responsibility: Given a failure query, retrieve similar past logs via the embedding service
and generate a root-cause summary using Claude API (RAG pattern).
"""
 
import os
import sys
from typing import List, Dict, Any
from dotenv import load_dotenv
import anthropic
 
# Ensure the repository root is on sys.path when running this module directly.
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
 
from src.embeddings.embedder import LogEmbeddingService
 
load_dotenv()    # loads ANTHROPIC_API_KEY from .env file
 
 
SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) specializing in
enterprise API gateway failures and CI/CD pipeline debugging.
 
You will be given:
1. A description of a current failure or alert
2. A set of similar past failure log entries retrieved from a production log database
 
Your job is to:
- Identify the most likely root cause based on the evidence
- List the 2-3 most probable causes in order of likelihood
- Provide specific, actionable remediation steps
- Flag if the pattern suggests a systemic issue vs. an isolated incident
 
Be specific. Reference the actual log content. Do not speculate beyond the evidence.
Format your response as:
 
ROOT CAUSE ANALYSIS
===================
Most Likely Cause: [one sentence]
 
Evidence from logs:
- [specific log evidence]
 
Possible Causes (ranked):
1. [cause] — [why]
2. [cause] — [why]
 
Remediation Steps:
1. [specific action]
2. [specific action]
 
Pattern Assessment: [Isolated incident / Systemic issue / Needs more data]
"""
 
 
class FailureAnalyzer:
    """
    Orchestrates the RAG pipeline: retrieve relevant logs -> generate LLM analysis.
    """
 
    def __init__(self, embedding_service: LogEmbeddingService = None):
        self.embedding_svc = embedding_service or LogEmbeddingService()
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("[WARN] ANTHROPIC_API_KEY not set. LLM calls will fail until set in environment or .env.")
            self.llm_client = None
        else:
            self.llm_client = anthropic.Anthropic(api_key=api_key)

        self.model = "claude-sonnet-4-6"
 
    def _build_context(self, similar_logs: List[Dict[str, Any]]) -> str:
        """Format retrieved log entries into a readable context block for the prompt."""
        if not similar_logs:
            return "No similar past failures found in the database."
 
        lines = ["SIMILAR PAST FAILURES (retrieved from log database):"]
        for i, log in enumerate(similar_logs, 1):
            lines.append(f"\n[Entry {i}] Similarity: {log['similarity_score']:.2f}")
            lines.append(f"  Timestamp: {log['metadata']['timestamp']}")
            lines.append(f"  Source: {log['metadata']['source']}")
            lines.append(f"  Severity: {log['metadata']['severity']}")
            lines.append(f"  Log text: {log['text']}")
        return "\n".join(lines)
 
    def analyze(self, failure_description: str, n_similar: int = 5) -> Dict[str, Any]:
        """
        Main entry point: given a failure description, return a root-cause analysis.
        Returns: dict with analysis text, retrieved_logs, and metadata.
        """
        print(f"[INFO] Retrieving similar failures for: {failure_description[:60]}...")
 
        # Step 1: Retrieve similar past failures from ChromaDB
        similar_logs = self.embedding_svc.search_similar(failure_description, n_results=n_similar)
        print(f"[INFO] Retrieved {len(similar_logs)} similar log entries")
 
        # Step 2: Build the RAG context string
        context = self._build_context(similar_logs)
 
        # Step 3: Construct the user message with context injected
        user_message = f"""CURRENT FAILURE DESCRIPTION:
{failure_description}
 
{context}
 
Based on this evidence, provide a root cause analysis following the format specified.
"""
 
        # Step 4: Call Claude API
        if not self.llm_client:
            msg = "LLM client not configured (missing ANTHROPIC_API_KEY)."
            print(f"[ERROR] {msg}")
            return {"error": msg, "retrieved_logs": similar_logs}

        print(f"[INFO] Calling Claude API ({self.model})...")
        try:
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

        except anthropic.BadRequestError as e:
            # Common when billing/credits are insufficient or request is malformed
            print(f"[ERROR] Anthropic BadRequestError: {e}")
            return {"error": "Anthropic BadRequestError: check API key and billing/credits.", "details": str(e), "retrieved_logs": similar_logs}
        except Exception as e:
            print(f"[ERROR] Anthropic API call failed: {type(e).__name__}: {e}")
            return {"error": f"Anthropic API call failed: {type(e).__name__}", "details": str(e), "retrieved_logs": similar_logs}

        analysis_text = response.content[0].text

        return {
            "analysis": analysis_text,
            "retrieved_logs": similar_logs,
            "model_used": self.model,
            "input_tokens": getattr(response.usage, 'input_tokens', None),
            "output_tokens": getattr(response.usage, 'output_tokens', None),
        }
 
 
# ── Smoke test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from src.ingestion.log_parser import parse_log_file
 
    # Seed the DB first if empty
    emb_svc = LogEmbeddingService()
    if emb_svc.count() == 0:
        entries = parse_log_file("data/sample_logs/layer7_failures.log")
        emb_svc.add_entries(entries)
 
    analyzer = FailureAnalyzer(embedding_service=emb_svc)
 
    test_query = """
    ALERT: API gateway cluster reporting 503 errors on /api/payments endpoint.
    Multiple clients affected. Certificate validation error suspected.
    Incident started 09:14 UTC.
    """
 
    result = analyzer.analyze(test_query)
    print("\n" + "="*60)
    if result is None:
        print("[ERROR] analyze() returned None")
    elif "error" in result:
        print(f"[ERROR] {result['error']}")
        if result.get("details"):
            print(result["details"])
    else:
        print(result["analysis"])
        print(f"\nTokens used: {result.get('input_tokens')} in / {result.get('output_tokens')} out")
