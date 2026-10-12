# Roadmap: External Benchmark Dataset Adaptation

This document specifies the technical design for evaluating ActionCloud against standard public AI agent benchmark datasets as an expansion beyond the built-in 136-task benchmark.

---

## 1. Motivation

The built-in benchmark (`src/actioncloud/benchmark/tasks.json`) was custom-tailored to evaluate:
1. Swarm-wide procedural knowledge reuse across 12 agent roles.
2. Prevention of redundant problem solving ($\text{RI}$).
3. Memory poisoning quarantine and epistemic tier transitions.

To validate ActionCloud's generalizability on external open-source software engineering repositories and diverse tool execution environments, we define an adapter architecture for two prominent external datasets:
- **SWE-bench** (Jimenez et al., ICLR 2024): 2,294 real-world GitHub issues from 12 popular Python repositories.
- **ToolBench / ToolLLM** (Qin et al., ICLR 2024): 16,464 real-world REST APIs across 49 categories.

---

## 2. Adaptation Architecture

Standard agent benchmarks test an isolated agent solving single issues from scratch ($k=0$ memory). To evaluate **ActionCloud**, tasks must be structured into **Clustered Issue Sequences** to measure cross-agent transfer.

```
External Dataset (SWE-bench / ToolBench)
                 │
                 ▼
     [Repository Clustering]
  (Group issues by repo, module, and error signature)
                 │
                 ▼
  [Sequential Agent Swarm Execution]
  ├── Agent 1: Solves Issue A (e.g., pytest fixture bug)
  │    └── Stores Experience in ActionCloud (tier: agent)
  │
  ├── Agent 2: Solves Related Issue B (same module/repo)
  │    ├── Hybrid Search retrieves Agent 1's playbook
  │    ├── Executes task using retrieved procedure
  │    └── Reports reuse outcome -> Memory Judge promotes to shared
  │
  └── Agent 3: Solves Related Issue C
       └── Reuses validated organizational playbook
```

---

## 3. Benchmark Adaptation Specifications

### A. SWE-bench Adapter (`SWE-bench / SWE-bench Lite`)
- **Dataset Source**: Real GitHub issue descriptions, codebases, and ground-truth pull request patch diffs (`test_patch` and `patch`).
- **Clustering Strategy**:
  - Cluster issues by repository (e.g., `scikit-learn`, `sympy`, `django`, `flask`).
  - Sub-cluster issues sharing common root dependencies or deprecated API patterns.
- **Evaluation Metrics**:
  - **Patch Resolution Rate (% Pass)**: Compared to stateless baseline.
  - **Token & Cost Reduction**: Reduction in input/output tokens for repository-specific diagnostic loops.
  - **Knowledge Reuse Rate (KRR)**: Frequency of successful procedure transfer between related repository bugs.

### B. ToolBench Adapter
- **Dataset Source**: Complex multi-turn tool trajectories involving authentication, REST headers, and multi-step API workflows.
- **Clustering Strategy**:
  - Group tasks by shared API suites (e.g., cloud storage APIs, payment gateway webhooks).
- **Evaluation Metrics**:
  - **Tool Call Reduction**: Drop in exploratory/failed tool invocations when procedural playbooks specify exact parameters and pitfalls.
  - **API Error Reduction Rate**: Reduction in HTTP 4xx/5xx responses due to retrieved prerequisite workflows.

---

## 4. Implementation Checklist for Future Phase

- [ ] Create `scripts/adapters/swebench_importer.py` to ingest SWE-bench Lite task JSONs into ActionCloud `TaskSpec` models.
- [ ] Implement `scripts/adapters/toolbench_importer.py` for API tool definitions.
- [ ] Set up Docker container sandboxes with repo git environments to execute patches.
- [ ] Run A/B evaluation: System A (Stateless Agent) vs System B (ActionCloud Memory Swarm).
