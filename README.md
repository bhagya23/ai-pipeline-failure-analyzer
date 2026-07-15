# AI Pipeline Failure Analyzer
 
> AI-powered root cause analysis for enterprise API gateway and CI/CD pipeline failures.
> Built with Python, LangChain, ChromaDB, and Claude/OpenAI API.
 
## Problem Statement
 
Enterprise API gateway failures (Layer7, Oracle Service Bus) and CI/CD pipeline
breakdowns cost engineering teams hours of manual log triage. This system ingests
raw failure logs, embeds them in a vector store for semantic search, and uses an LLM
to generate actionable root-cause summaries — reducing triage time from hours to minutes.
 
## Architecture
 
```
Raw Logs (Layer7 / GitLab CI)
         |
         v
  [Log Ingestion Service]  <-- src/ingestion/log_parser.py
         |
         v
  [Embedding Service]      <-- src/embeddings/embedder.py
  (ChromaDB Vector Store)
         |
         v
  [LLM Analysis Service]   <-- src/llm/analyzer.py
  (Claude / OpenAI API)
         |
         v
  [REST API / Dashboard]   <-- src/api/main.py
  Root Cause Summary + Fix Suggestions
```
 
## Tech Stack
 
| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| AI Framework | LangChain |
| Vector Store | ChromaDB |
| LLM | Claude API (Anthropic) / OpenAI |
| API | FastAPI |
| Infra | Docker, Terraform, AWS ECS |
| Observability | Prometheus + Grafana |
 
## Project Status
 
- [x] Project scaffold and architecture defined
- [ ] Log ingestion module (in progress)
- [ ] Vector embedding pipeline
- [ ] LLM root cause analysis
- [ ] REST API layer
- [ ] Docker containerization
- [ ] Cloud deployment (AWS ECS)
 
## Setup
 
```bash
git clone https://github.com/bhagya23/ai-pipeline-failure-analyzer.git
cd ai-pipeline-failure-analyzer
pip install -r requirements.txt
cp .env.example .env  # add your API keys
```
## Known Issues & Development Notes

While building this locally on Windows, I ran into and resolved a few environment and logic issues worth documenting:

### 1. Windows security policies blocking native ML library DLLs
**Symptom:** `ImportError: DLL load failed while importing _sfc64: An Application Control policy has blocked this file.`

**Investigation:** Initially suspected Windows Defender, since it's the more common cause of this class of error. Added Defender exclusions for `python.exe` and the `torch` package directory, and allowed `python.exe` under Controlled Folder Access. This did not resolve the issue — the same error persisted, ruling out Defender as the actual cause.

**Actual root cause:** Windows Smart App Control (enabled by default on some Windows 11 installations), which blocks certain native DLLs used by NumPy/SciPy that sentence-transformers depends on transitively via scikit-learn.

**Fix:** Disabled Smart App Control via Windows Security → App & browser control → Smart App Control. If already fully enabled and evaluated, a clean Windows reinstall is required instead — this is intentional Microsoft design, not a bug.

**Defensive coding added regardless:** Wrapped the `SentenceTransformerEmbeddingFunction(...)` initialization in `embedder.py` in a try/except that catches the Torch-load failure and falls back to ChromaDB's default embedding function instead of crashing. This means the pipeline degrades gracefully on any future environment where the specified model can't load, rather than hard-failing — useful defensive design even now that the root cause is fixed, since it protects against similar issues in other environments (e.g., a teammate's machine, a future OS update).

**Result:** With Smart App Control disabled, the intended `all-MiniLM-L6-v2` model now loads and runs correctly; the try/except fallback remains in the code as a safety net, not because it's currently needed.

### 2. Blank lines in log files are silently skipped (expected behavior)
**Symptom:** `[INFO] Parsed 29 entries, skipped 11 lines from ...` even though the log file "looks like" it only has valid entries.

**Cause:** Not a bug — the log file had 11 blank lines mixed in (from copy/paste formatting), and `parse_line()` intentionally returns `None` for empty lines without printing a warning, since blank lines aren't malformed input.

**Verify line counts on Windows (PowerShell doesn't have `wc -l`):**
\`\`\`powershell
(Get-Content data/sample_logs/layer7_failures.log).Count
(Get-Content data/sample_logs/layer7_failures.log | Where-Object { $_.Trim() -ne "" }).Count
\`\`\`

### 3. ChromaDB embedding function conflict after switching embedding models
**Symptom:** `ValueError: An embedding function already exists in the collection configuration, and a new one is provided.`

**Cause:** ChromaDB persists which embedding function created a collection. After fixing the Smart App Control issue and switching from the fallback embedding function to the intended sentence-transformer model, ChromaDB correctly refuses to mix embeddings from two different models in the same collection, since they aren't mathematically comparable.

**Fix:** Delete the persisted ChromaDB data directory and let it recreate cleanly:
\`\`\`powershell
Remove-Item -Recurse -Force data\chroma_db
\`\`\`

### 4. get_error_summary() was defined after __main__ and never invoked, plus missing a severity filter
**Symptom:** No "Error Summary" output appeared at all when running the script, despite the function existing in the file.

**Cause:** Two separate issues: (1) the function was defined *after* the `if __name__ == "__main__":` block, so it was never called; (2) the function counted all entries per source regardless of severity, rather than filtering to `severity == "ERROR"` — meaning even once wired in, it would have returned inflated, incorrect counts.

**Fix:** Moved the function definition above the `__main__` block (standard Python convention), added an explicit filter (`if not source or severity != "ERROR": continue`), and added a call to the function with printed output inside `__main__`.

**Lesson:** A function's name and presence in a file don't guarantee it does what it claims, or that it's even being executed — always verify actual printed output against expected values rather than assuming correctness from code review alone.

## Author
 
Bhagyashree Sahoo | Senior Platform Engineer | 10+ years enterprise integration
LinkedIn: linkedin.com/in/bhagyashree-sahoo2392
