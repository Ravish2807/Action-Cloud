# ActionCloud Journal Readiness & Publication Progress

This document tracks the execution and verification of journal submission requirements for ActionCloud across IEEE and Elsevier formats.

## Phase 1: Manuscript Metadata & Editorial Finalization
- **Status**: Completed
- **Target Venues**: 
  - Primary: *IEEE Transactions on Cloud Computing* (using `main.tex`, IEEEtran 2-column format)
  - Alternate: *Elsevier Future Generation Computer Systems* (using `main_elsarticle.tex`, 5p format)
- **Author Information**:
  - Naga Shiva (Corresponding Author: `nagashiva@cb.students.amrita.edu`)
  - Rajashree
  - Ravishanmugam (`ravish2007821@gmail.com`)
  - Sharvesh
  - Affiliation: Amrita School of Artificial Intelligence, Amrita Vishwa Vidyapeetham, Coimbatore, India
- **CRediT Roles**: Defined in `main_elsarticle.tex`.
- **AI-Assisted Technology Disclosure**: Added to both IEEE `Acknowledgment` and Elsevier declaration blocks.
- **Highlights**: Verified 5 bullets ($\le 85$ characters each) in `highlights.txt`.

## Phase 2: Experimental Strengthening
- **Status**: Completed
- **Embedding Calibration**: Calibrated lexical hashing embedder ($\tau = 0.30$, $90.58\%$ recall, $1.02\%$ FPR; $\tau = 0.40$ raises precision to $91.95\%$ but drops recall to $57.97\%$). Documented semantic embedding transition to $\tau \approx 0.70$ for zero-lexical overlap settings.
- **Baseline Positioning**: Enriched comparative analysis distinguishing ActionCloud's anti-poisoning procedural governance from Mem0 (conversational user preference extraction) and MemClaw (tenant isolation).
- **Model Adapter Architecture**: Multi-provider support verified in `llm.py` across `sim`, `gemini-1.5-flash`, `groq/llama-3.3-70b`, and `claude-3-5-sonnet`.

## Phase 3: Cloud Systems & Architectural Profiling
- **Status**: Completed
- **Asynchronous Ingestion**: Codified decoupled Amazon SQS architecture (`POST /experiences` returns `202 Accepted` in 1.8 ms p50, with background worker consuming via long-polling and DLQ poison message isolation).
- **Cloud Infrastructure as Code**: Documented production AWS EKS Terraform stack, private Multi-AZ RDS PostgreSQL with pgvector, Helm microservices charts, Horizontal Pod Autoscaling (HPA), Pod Disruption Budgets (PDB), and Prometheus telemetry integration.

## Phase 4: Verification, Build & Packaging
- **Status**: Completed
- **BibTeX Verification**: All 29 reference entries in `refs.bib` audited and verified with proper citation keys.
- **Manuscript Packages**: Both IEEE (`main.tex` / `main.pdf`) and Elsevier FGCS (`main_elsarticle.tex` / `main_elsarticle.pdf`) preserved and updated in `C:\AIE Files\Projects\S5\Cloud Computing\D14\`.
- **Source Code & Data Repository**: Synchronized on GitHub `main` branch with reproducible seeds and automated test suites.
