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
 
## Author
 
Bhagyashree Sahoo | Senior Platform Engineer | 10+ years enterprise integration
LinkedIn: linkedin.com/in/bhagyashree-sahoo2392
