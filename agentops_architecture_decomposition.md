# AgentOps Architecture Decomposition

**Diagram Title**: AgentOps Multi-Environment Single-Account Multi-Agent View

## Overview

This document is a comprehensive decomposition of the AgentOps V1 architecture diagram. It is intended to give an agent or developer a complete, accurate understanding of every component, connection, environment, and process shown in the diagram — sufficient to continue development, extend the system, or implement any part of it from scratch.

The architecture implements a **multi-environment CI/CD pipeline** for developing, testing, promoting, and monitoring AI agents. It uses Databricks (Unity Catalog, MLflow, Model Serving) as the core platform, with Git-based branching as the environment promotion mechanism.

### Architectural Layers (top to bottom in the diagram)

| Layer | Description |
|---|---|
| **Git Provider** | Source of truth; branch strategy drives environment promotion |
| **Development Workspace** | Where agents are built, iterated on, and locally validated |
| **Staging Workspace** | CI-triggered automated testing gate before production |
| **Production Workspace** | Live environment receiving promoted, tested agents |
| **Unity Catalog / Lakehouse** | Shared governed data layer spanning all environments |

---

## Visual / Diagram Coding Reference

Understanding the visual language of the diagram is essential for reading it accurately.

| Visual Style | Meaning |
|---|---|
| Purple solid-border box | **Workflow** — a multi-step orchestrated process (e.g., Databricks Workflow) |
| Purple dashed-border box | **Job / Workflow task** — an individual task within a workflow |
| Green dashed-border box | **CI/CD pipeline step** — automated pipeline action |
| Pink/salmon dashed-border box | **Interface** — a system or catalog boundary |
| Blue solid arrow (`→`) | **Reads** — data read from a source |
| Black solid arrow (`→`) | **Writes** — data written to a destination |
| Dashed dark/maroon arrow | **MLflow API call** — MLflow tracing or logging call |
| Orange-bordered rectangle | **SME Human-in-the-loop Feedback** node |
| Orange hexagon | **External endpoint** (Model Serving Endpoint) |
| `ψ_<branch>` icon | **Git branch marker** — indicates which branch the component runs on |
| Red diamond icon | **Git repository** |
| Git branch icon | **Git branch** |
| Registered model icon | MLflow-registered model in Unity Catalog |
| Registered AI Tools & Functions icon | Registered tool/function in Unity Catalog |
| Delta Lake icon | Delta Lake table asset |

---

## Layer 1: Git Provider (Top Row)

The Git Provider section spans the entire top of the diagram. A **single ML Project Repo** (Git repository) appears three times, representing the same repo viewed at different branch states as code is promoted through environments.

### ML Project Repo — Three Branch States

| Position | Branch | Role |
|---|---|---|
| Left (above Dev) | `dev` | Active development branch; developer commits target here |
| Center (above Staging) | `main` | CI merge target; code lands here after staging passes |
| Right (above Prod) | `release` | Production promotion target; triggers Continuous Deployment |

### Git Flow Sequence (Left → Right)

```
1. Create dev branch          ← developer action (from ML Project Repo)
2. Commit code                ← developer pushes to dev branch
3. CI trigger                 ← automatic; fires when dev branch pushed
4. [Staging tests run]
5. Merge                      ← merge dev → main after staging passes
6. Merge into release         ← merge main → release branch
7. Continuous Deployment      ← green-dashed CI/CD pipeline box; fires on release branch
8. [Deploy to Production]     ← output of Continuous Deployment pipeline
```

### Continuous Deployment Box
- **Type**: CI/CD pipeline step (green dashed border)
- **Branch**: `release`
- **Purpose**: The final automated step that takes the `release` branch and deploys it into the Production workspace. This is the bridge between the Git layer and the Production workspace.

---

## Layer 2: Development Workspace

**Background color**: Light blue (`#cfe4ff`)
**Purpose**: Where agents are built, iterated on, and validated before being promoted to CI/CD.

The Development workspace contains five major functional areas:

1. MLflow Tracking Server (center-top)
2. SME Human-in-the-loop Feedback (top-right)
3. Model Serving Endpoint (right)
4. Data Preparation Workflow (left)
5. Agent Development Workflow (center)
6. App Deployment Workflow (right)

---

### 2.1 MLflow Tracking Server (Development)

**Visual style**: Dashed blue border (MLflow API interface)
**Position**: Center-top of the Development workspace

**What it does**: The central observability hub for development. Captures agent evaluation traces, experiment metrics, and human feedback. Enables developers and SMEs to inspect agent behavior and quality before promotion.

**Connections**:

| Connection | Direction | Label | Source/Target |
|---|---|---|---|
| Feedback Trace Logging | ← Inbound | from SME Human-in-the-loop Feedback | Human reviewer sends feedback traces here |
| Trace & Evaluation Logging | → Outbound | to Agent Development Workflow | Surfaces traces to agent eval steps |

**Key behavior**: All agent evaluation runs in the Agent Development Workflow log their traces here via the MLflow API (dashed line connection). SME reviewers access these traces to provide structured feedback.

---

### 2.2 SME Human-in-the-loop Feedback

**Visual style**: Orange-bordered rectangle
**Position**: Top-right of Development workspace

**What it does**: Represents a Subject Matter Expert (domain expert or QA reviewer) who manually reviews agent outputs and trace quality. This is the human gate in the development loop — before code is promoted, a human validates that the agent is behaving correctly.

**Connections**:

| Connection | Direction | Target |
|---|---|---|
| Feedback Trace Logging | → to MLflow Tracking Server | Human sends structured feedback into MLflow |
| (implicit) | ← reads from | Model Serving Endpoint (reviews live agent outputs) |

**Why it matters**: Human feedback captured in MLflow creates an auditable record of quality checks at the development stage.

---

### 2.3 Model Serving Endpoint

**Visual style**: Orange hexagon
**Position**: Right side of Development workspace, between Agent Dev Workflow and App Deployment Workflow

**What it does**: A live Databricks Model Serving endpoint that hosts the currently deployed dev-branch agent. Used for:
- Manual evaluation by SME reviewers
- Real-time inference during development testing

**Connections**:

| Connection | Direction | Source |
|---|---|---|
| Deploy | ← from App Deployment Workflow | Agent app is deployed to this endpoint |
| (calls) | ← from SME Feedback node | SME reviewer calls the endpoint for manual testing |

---

### 2.4 Data Preparation Workflow

**Visual style**: Purple solid-border (Workflow)
**Branch**: `ψ_dev`
**Position**: Left side of Development workspace

**What it does**: Prepares all data assets required by agents — both structured (tables) and unstructured (documents) — and writes them into the Dev Catalog. This workflow must run before agents can be trained or evaluated.

#### Sub-components (sequential execution):

**Structured data pipeline**:

| Step | Type | What it does |
|---|---|---|
| **Data Ingestion** | Job/task (purple dashed) | Pulls raw source data into the pipeline |
| **Chunking** | Job/task (purple dashed) | Splits documents or records into semantic chunks for embedding |
| **Vector Search Indexing** | Job/task (purple dashed) | Generates embeddings and builds the vector search index in Dev Catalog |

**Unstructured Data Extraction** (sub-workflow, purple solid-border):

| Step | Type | What it does |
|---|---|---|
| **`ai_parse_document`** | Job/task (purple dashed) | Uses AI to parse unstructured documents (PDFs, HTML, etc.) |
| **`ai_query_extraction`** | Job/task (purple dashed) | Extracts structured, query-relevant information from parsed documents |
| **Data Preparation** | Job/task (purple dashed) | Final formatting and normalization before catalog write |

**Data flow**:
- **Reads from**: Prod Catalog (Read Only) — Tables, Models — via Unity Catalog
- **Writes to**: Dev Catalog — Vector Search index, Tables

---

### 2.5 Agent Development Workflow

**Visual style**: Purple solid-border (Workflow)
**Branch**: `ψ_dev`
**Position**: Center of Development workspace (largest section)

**What it does**: The core iterative agent build loop. Developers build agent logic, register tools and functions, and run automated evaluations — all within this workflow.

#### Sub-components:

| Component | Type | What it does |
|---|---|---|
| **Agent Router Development** | Job/task (purple dashed) | Builds the dispatcher that routes incoming requests to the correct agent (Agent 1, Agent 2, or others). The router is the single entry point for the multi-agent app. |
| **Agent 1 Tool & Function Library** | Job/task (purple dashed) | Registers Agent 1's tools and functions into Dev Catalog (AI Tools & Functions asset). These are the callable functions available to Agent 1 at inference time. |
| **Agent 1 Development** | Job/task (purple dashed) | Iterative development of Agent 1's system prompt, logic, retrieval strategy, and tool-calling behavior. |
| **Agent 2 Tool & Function Library** | Job/task (purple dashed) | Registers Agent 2's tools and functions into Dev Catalog (AI Tools & Functions asset). |
| **Agent 2 Development** | Job/task (purple dashed) | Iterative development of Agent 2. |
| **Agent 1 Automated Evaluation** | Job/task (purple dashed) | Runs the automated evaluation suite against Agent 1. Logs all evaluation traces and metrics to the MLflow Tracking Server. This is the automated quality gate for Agent 1. |
| **Agent 2 Automated Evaluation** | Job/task (purple dashed) | Runs the automated evaluation suite against Agent 2. Logs traces and metrics to MLflow. |

**Data flow**:
- **Reads from**: Dev Catalog — Vector Search, AI Tools & Functions, Tables, Models
- **Writes to**: MLflow Tracking Server — via "Trace & Evaluation Logging" (MLflow API, dashed line)

**Note**: Agent 1 and Agent 2 are developed in parallel tracks within the same workflow. The Agent Router ties them together at deployment time.

---

### 2.6 App Deployment Workflow

**Visual style**: Purple solid-border (Workflow)
**Branch**: `ψ_dev`
**Position**: Right side of Development workspace

**What it does**: Assembles and deploys the complete multi-agent application to the dev environment. This is the final step before a developer commits and triggers CI.

#### Sub-components:

| Component | Type | What it does |
|---|---|---|
| **Agent 1 Deployment** | Job/task (purple dashed) | Packages and deploys Agent 1 |
| **Agent 2 Deployment** | Job/task (purple dashed) | Packages and deploys Agent 2 |
| **App Deployment** | Job/task (purple dashed) | Deploys the full multi-agent application (Router + Agent 1 + Agent 2) |

**Data flow**:
- **Reads from**: Prod Catalog (Read Only) and Dev Catalog
- **Deploys to**: Model Serving Endpoint (orange hexagon)

---

## Layer 3: Staging Workspace

**Background color**: Orange
**Branch**: `ψ_staging`
**Trigger**: Automatic — fires when CI trigger activates from a `dev` branch commit

**Purpose**: An automated quality gate. No human intervention is expected here. The staging workspace runs three tiers of automated tests and logs everything to MLflow. If all tests pass, the code is promoted to the `release` branch.

---

### 3.1 MLflow Tracking Server (Staging)

**Visual style**: Dashed blue border (MLflow API interface)

**What it does**: Receives all test logging from the CI test suite. Provides a queryable record of every test run, making it possible to audit what was tested and what passed/failed before any production promotion.

**Connection**: **Test Logging** — receives from all three CI test boxes.

---

### 3.2 CI Test Suite

All three test types run on the `staging` branch. They all **read from the Dev Catalog** (Vector Search, AI Tools & Functions, Tables, Models — blue upward arrows from the catalog). Results are logged to the MLflow Tracking Server.

| Test | Visual style | What it validates |
|---|---|---|
| **Unit tests (CI)** | Green dashed (CI/CD pipeline) | Isolated unit tests of individual agent components, tool functions, and logic modules. Fast, no external dependencies. |
| **Integration tests (CI)** | Green dashed (CI/CD pipeline) | Tests the agent's interaction with external systems: Dev Catalog reads, MLflow API calls, tool function invocations. Confirms end-to-end data plumbing works. |
| **Validation tests (CI)** | Green dashed (CI/CD pipeline) | End-to-end agent quality validation. Tests the agent's actual outputs against expected behavior/quality thresholds. The highest-stakes test tier. |

**Promotion condition**: All three test tiers must pass. Failure in any tier blocks promotion to `release`.

---

## Layer 4: Production Workspace

**Background color**: Green
**Branch**: `ψ_release`
**Trigger**: Continuous Deployment pipeline fires automatically when `release` branch receives a merge

**Purpose**: The live production environment. Serves real users (via Model Serving Endpoint), runs batch jobs (via Batch Inferencing), and continuously logs traces to MLflow for ongoing quality monitoring.

---

### 4.1 MLflow Tracking Server (Production)

**Visual style**: Dashed blue border (MLflow API interface)

**What it does**: Receives **Production Trace Logging** from all deployed agents and batch inference jobs. This enables:
- Ongoing monitoring of production agent quality
- Detection of model or data drift
- Comparison of production behavior against dev/staging baselines
- Feeding production traces back for future evaluation dataset construction

---

### 4.2 App Deployment Workflow (Production)

**Visual style**: Purple solid-border (Workflow)
**Branch**: `ψ_release`

This is the production mirror of the dev App Deployment Workflow, but deployed from the `release` branch.

#### Sub-components:

| Component | What it does |
|---|---|
| **Agent Router Deployment** | Production routing layer. Dispatches incoming requests to Agent 1 or Agent 2. |
| **Agent 1 Deployment** | Production Agent 1 — serving live traffic. |
| **Agent 2 Deployment** | Production Agent 2 — serving live traffic. |
| **App Deployment** | The complete deployed multi-agent application package. |

**Data flow**:
- **Reads from**: Prod Catalog (Vector Search, AI Tools & Functions, Tables, Models)
- **Writes to**: Prod Catalog (output tables, inference results)
- **Serves via**: Model Serving Endpoint

---

### 4.3 Batch Inferencing

**Visual style**: Purple solid-border (Workflow)
**Position**: Below App Deployment Workflow in the Production workspace

**What it does**: Runs scheduled or triggered batch inference jobs against the deployed production agents. Use cases include:
- Large-scale document processing
- Scheduled summarization or extraction pipelines
- Offline evaluation over new data

**Connections**:
- **Calls**: Model Serving Endpoint (orange hexagon) — submits inference requests to the live endpoint
- **Writes to**: Prod Catalog — batch results stored as Delta Lake tables
- **Logs to**: MLflow Tracking Server — via Production Trace Logging

---

## Layer 5: Unity Catalog / Lakehouse (Bottom Band)

**Visual style**: Pink/salmon dashed border (Interface)
**Position**: Bottom row, spanning the full width of the diagram
**Label**: "Unity Catalog" (left) and "Lakehouse" (bottom, spanning full width)

The Unity Catalog is the **single governed data plane** for all environments. Access is controlled at the catalog level — Dev workspace gets Dev Catalog (read/write) and Prod Catalog (read-only); Production workspace gets Prod Catalog (read/write).

---

### 5.1 Prod Catalog — Read Only (left side, accessible from Dev workspace)

**Visual style**: Dashed border sub-region within Unity Catalog
**Access from Dev**: **Read-only** (enforced by Unity Catalog permissions)

| Asset | Icon | Description |
|---|---|---|
| **Tables** | Delta Lake icon | Production Delta Lake tables. Dev agents can read prod data for baseline comparison. |
| **Models** | Registered model icon | Production MLflow-registered models. Dev can read prod models as a baseline for evaluation. |

**Key constraint**: Dev workspace agents and workflows **cannot write** to this catalog. This prevents accidental corruption of production data during development.

**Red arrow from Prod Catalog → Dev Catalog**: Production-registered models flow into the Dev Catalog as a baseline reference, enabling developers to compare their new models against the current production model.

---

### 5.2 Dev Catalog (writable — accessible from Dev and Staging workspaces)

**Visual style**: Dashed border sub-region (blue dashed, MLflow-style)
**Access**: Read/write from Development workspace; Read-only from Staging workspace

| Asset | Icon | Description |
|---|---|---|
| **Vector Search** | Search icon | Vector search index built by the Data Preparation Workflow. Agents use this for retrieval-augmented generation (RAG). |
| **AI Tools & Functions** | Tools icon | Registered callable tools and functions for Agent 1 and Agent 2. Defined and registered by the Tool & Function Library steps. |
| **Tables** | Delta Lake icon | Dev Delta Lake tables used during development and CI testing. |
| **Models** | Registered model icon | MLflow-registered dev models. Created during agent development and evaluation. |

**Write sources**: Data Preparation Workflow (Vector Search, Tables), Agent Development Workflow (AI Tools & Functions, Models)
**Read sources**: Agent Development Workflow, App Deployment Workflow, all three Staging CI test types

---

### 5.3 Prod Catalog (right side, accessible from Production workspace)

**Access**: Read/write from Production workspace only

| Asset | Icon | Description |
|---|---|---|
| **Vector Search** | Search icon | Production vector search index for live agent RAG. |
| **AI Tools & Functions** | Tools icon | Production-registered tools and functions. |
| **Tables** | Delta Lake icon | Production Delta Lake tables. Written to by deployed agents and Batch Inferencing. |
| **Models** | Registered model icon | Production MLflow-registered models. |

**Write sources**: App Deployment Workflow (production outputs), Batch Inferencing (batch results)
**Read sources**: App Deployment Workflow (agent reads its own catalog), Batch Inferencing

---

### 5.4 Lakehouse

The underlying physical storage for all Unity Catalog assets. All catalogs (Dev Catalog, Prod Catalog) and all asset types (tables, models, vector indexes, functions) are physically stored in the Lakehouse via Delta Lake. The Lakehouse label appears at the very bottom of the diagram, spanning the full width.

---

## End-to-End CI/CD Flow

```
╔══════════════════════════════════════════════════════════════════╗
║  DEVELOPER LOOP (Development Workspace, branch: dev)             ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  1. Create dev branch from ML Project Repo                       ║
║                                                                  ║
║  2. Data Preparation Workflow:                                   ║
║     Data Ingestion                                               ║
║       → Chunking                                                 ║
║         → Vector Search Indexing ──────────────► Dev Catalog     ║
║     Unstructured Data Extraction:                                ║
║       ai_parse_document                                          ║
║         → ai_query_extraction                                    ║
║           → Data Preparation ─────────────────► Dev Catalog     ║
║                                                                  ║
║  3. Agent Development Workflow:                                  ║
║     Agent Router Development                                     ║
║     Agent 1 Tool & Function Library ──────────► Dev Catalog      ║
║     Agent 1 Development                                          ║
║     Agent 2 Tool & Function Library ──────────► Dev Catalog      ║
║     Agent 2 Development                                          ║
║     Agent 1 Automated Evaluation ─────────────► MLflow (dev)     ║
║     Agent 2 Automated Evaluation ─────────────► MLflow (dev)     ║
║                                                                  ║
║  4. SME Human-in-the-loop Feedback:                             ║
║     SME reviews traces in MLflow                                 ║
║     SME tests agents via Model Serving Endpoint                  ║
║     Feedback Trace Logging ───────────────────► MLflow (dev)     ║
║                                                                  ║
║  5. App Deployment Workflow:                                     ║
║     Agent 1 Deployment + Agent 2 Deployment                      ║
║     App Deployment ────────────────────────► Model Serving EP    ║
║                                                                  ║
║  6. Commit code → ML Project Repo (dev branch)                   ║
╚══════════════════════════════════════════════════════════════════╝
                          │
                          │ CI trigger
                          ▼
╔══════════════════════════════════════════════════════════════════╗
║  CI GATE (Staging Workspace, branch: staging)                    ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Unit tests (CI) ─────────────────────────────► MLflow (staging) ║
║  Integration tests (CI) ──────────────────────► MLflow (staging) ║
║  Validation tests (CI) ───────────────────────► MLflow (staging) ║
║                                                                  ║
║  All tests read from Dev Catalog                                 ║
║  All results logged to MLflow Tracking Server                    ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
                          │
              ┌───────────┴────────────┐
              │ Tests pass             │ Tests fail
              ▼                       ▼
       Merge → main           ← Block promotion
              │
       Merge into release
              │
    Continuous Deployment
    (CI/CD pipeline, green-dashed)
              │
              ▼
╔══════════════════════════════════════════════════════════════════╗
║  PRODUCTION (Production Workspace, branch: release)              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  App Deployment Workflow:                                        ║
║    Agent Router Deployment                                       ║
║    Agent 1 Deployment                                            ║
║    Agent 2 Deployment                                            ║
║    App Deployment ◄── reads Prod Catalog                         ║
║                   ──► writes Prod Catalog                        ║
║                                                                  ║
║  Batch Inferencing:                                              ║
║    Calls Model Serving Endpoint                                  ║
║    Writes results ──────────────────────────► Prod Catalog       ║
║    Logs traces ─────────────────────────────► MLflow (prod)      ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Cross-Workspace Connection Map

| Source | Arrow Type | Target | Semantic Meaning |
|---|---|---|---|
| Dev Catalog (Vector Search) | Blue (Reads) | Agent Development Workflow | Agents do RAG from dev vector index |
| Dev Catalog (AI Tools & Functions) | Blue (Reads) | Agent Development Workflow | Agents invoke dev-registered tools |
| Dev Catalog (Tables, Models) | Blue (Reads) | Agent Development Workflow | Agents read dev data and models |
| Dev Catalog (all assets) | Blue (Reads) | Staging Unit/Integration/Validation tests | CI tests read dev catalog assets |
| Prod Catalog (Tables, Models) | Red arrow | Dev Catalog | Prod models used as dev baseline |
| Prod Catalog (Read Only) | Blue (Reads) | Data Preparation Workflow | Dev data prep reads prod data |
| MLflow Tracking Server (dev) | Dashed MLflow | SME Feedback node | Traces surfaced to human reviewer |
| SME Feedback | Feedback Trace Logging | MLflow Tracking Server (dev) | Human feedback recorded in MLflow |
| App Deployment Workflow (dev) | Deploy | Model Serving Endpoint | Agent app deployed to dev endpoint |
| Batch Inferencing (prod) | Calls | Model Serving Endpoint | Batch jobs call live serving endpoint |
| App Deployment Workflow (prod) | Black (Writes) | Prod Catalog | Production inference outputs stored |
| Prod Catalog | Blue (Reads) | App Deployment Workflow (prod) | Production agents read prod assets |
| All CI test boxes | MLflow (Test Logging) | MLflow Tracking Server (staging) | All test results logged to staging MLflow |
| Production agents | Production Trace Logging | MLflow Tracking Server (prod) | Ongoing production quality monitoring |

---

## Key Architectural Principles

### 1. Branch = Environment
`dev` → Development workspace; `staging` → Staging; `release` → Production. Branch promotion **is** environment promotion. There is no manual deploy step — the CI/CD pipeline handles it.

### 2. MLflow Tracing in Every Environment
Every workspace has its own MLflow Tracking Server. Observability is a first-class citizen at every stage — development evals, CI test results, and production traces are all captured in MLflow.

### 3. Read-Only Prod Catalog from Dev
The Development workspace can read production data (for baseline comparison) but cannot write to it. This is enforced via Unity Catalog permissions and prevents accidental pollution of production data.

### 4. Automated Evaluation Gates
Agents must pass Agent 1 Automated Evaluation and Agent 2 Automated Evaluation within the Agent Development Workflow before the developer commits and triggers CI. This creates a pre-commit quality gate.

### 5. Human-in-the-Loop at Dev Stage
The SME Human-in-the-loop Feedback node provides a human quality check during development — before CI is triggered. Feedback is structured and logged to MLflow, making it auditable and available for future training.

### 6. Multi-Agent with Shared Router
The architecture uses a dedicated **Agent Router** (developed in Agent Router Development, deployed in Agent Router Deployment). The router is the single entry point for the application, dispatching to specialized agents. This makes it easy to add Agent 3, Agent 4, etc. without changing the client interface.

### 7. Registered Assets Govern Promotion
All agent capabilities (tools, functions, vector indexes, models) are registered as assets in Unity Catalog. The Dev Catalog holds dev-stage assets; the Prod Catalog holds promoted assets. Promotion happens through the CI/CD pipeline, not manual catalog writes.

### 8. Batch + Real-Time in Production
Production supports two inference modalities:
- **Real-time**: App Deployment Workflow → Model Serving Endpoint (orange hexagon)
- **Batch**: Batch Inferencing → calls Model Serving Endpoint → writes to Prod Catalog

Both modalities log to MLflow for unified observability.

### 9. Single-Account, Multi-Environment
All three workspaces (Dev, Staging, Prod) run within the same Databricks account and share one Unity Catalog instance. Environment isolation is achieved through:
- Separate catalog namespaces (Dev Catalog vs. Prod Catalog)
- Catalog-level access controls (read-only vs. read-write permissions)
- Branch-based workspace separation

This avoids the complexity of multi-account setups while maintaining strong data governance boundaries.

---

## Component Inventory by Environment

### Development Workspace Components

| Component | Type | Branch | Primary Inputs | Primary Outputs |
|---|---|---|---|---|
| MLflow Tracking Server | Interface (dashed blue) | dev | Traces, Feedback | Trace & Evaluation Logging |
| SME Human-in-the-loop Feedback | Orange rectangle | dev | Agent outputs via endpoint | Feedback Trace Logging → MLflow |
| Model Serving Endpoint | Orange hexagon | dev | Deployed agent app | Live inference |
| Data Ingestion | Job/task | dev | Raw source data | Raw pipeline data |
| Chunking | Job/task | dev | Raw data | Document chunks |
| Vector Search Indexing | Job/task | dev | Chunks | Dev Catalog: Vector Search |
| ai_parse_document | Job/task | dev | Unstructured docs | Parsed documents |
| ai_query_extraction | Job/task | dev | Parsed docs | Extracted structured content |
| Data Preparation | Job/task | dev | Extracted content | Dev Catalog: Tables |
| Agent Router Development | Job/task | dev | Agent definitions | Router logic |
| Agent 1 Tool & Function Library | Job/task | dev | Tool definitions | Dev Catalog: AI Tools & Functions |
| Agent 1 Development | Job/task | dev | Dev Catalog assets | Agent 1 logic/prompts |
| Agent 2 Tool & Function Library | Job/task | dev | Tool definitions | Dev Catalog: AI Tools & Functions |
| Agent 2 Development | Job/task | dev | Dev Catalog assets | Agent 2 logic/prompts |
| Agent 1 Automated Evaluation | Job/task | dev | Agent 1 | MLflow: evaluation traces |
| Agent 2 Automated Evaluation | Job/task | dev | Agent 2 | MLflow: evaluation traces |
| Agent 1 Deployment | Job/task | dev | Agent 1 | Deployed Agent 1 |
| Agent 2 Deployment | Job/task | dev | Agent 2 | Deployed Agent 2 |
| App Deployment | Job/task | dev | All agents + router | Model Serving Endpoint |

### Staging Workspace Components

| Component | Type | Branch | Primary Inputs | Primary Outputs |
|---|---|---|---|---|
| MLflow Tracking Server | Interface (dashed blue) | staging | Test results | Test Logging |
| Unit tests (CI) | CI/CD pipeline step | staging | Dev Catalog assets | Pass/fail + MLflow logs |
| Integration tests (CI) | CI/CD pipeline step | staging | Dev Catalog assets | Pass/fail + MLflow logs |
| Validation tests (CI) | CI/CD pipeline step | staging | Dev Catalog assets | Pass/fail + MLflow logs |

### Production Workspace Components

| Component | Type | Branch | Primary Inputs | Primary Outputs |
|---|---|---|---|---|
| MLflow Tracking Server | Interface (dashed blue) | release | Production traces | Production Trace Logging |
| Agent Router Deployment | Job/task | release | Release branch | Routing logic in prod |
| Agent 1 Deployment | Job/task | release | Release branch | Production Agent 1 |
| Agent 2 Deployment | Job/task | release | Release branch | Production Agent 2 |
| App Deployment | Job/task | release | All agents + router | Live multi-agent app |
| Batch Inferencing | Workflow | release | Model Serving Endpoint | Prod Catalog: results |

### Unity Catalog Assets

| Catalog | Asset | Access Level | Written By | Read By |
|---|---|---|---|---|
| Prod Catalog (dev-facing) | Tables | Read-only from dev | Production agents | Dev Data Preparation |
| Prod Catalog (dev-facing) | Models | Read-only from dev | CI/CD promotion | Dev Agent Development |
| Dev Catalog | Vector Search | Read/write from dev | Data Preparation Workflow | Agent Development, Staging tests |
| Dev Catalog | AI Tools & Functions | Read/write from dev | Tool & Function Libraries | Agent Development, Staging tests |
| Dev Catalog | Tables | Read/write from dev | Data Preparation Workflow | Agent Development, Staging tests |
| Dev Catalog | Models | Read/write from dev | Agent Development Workflow | Agent Development, Staging tests |
| Prod Catalog (prod-facing) | Vector Search | Read/write from prod | CI/CD promotion | Production agents |
| Prod Catalog (prod-facing) | AI Tools & Functions | Read/write from prod | CI/CD promotion | Production agents |
| Prod Catalog (prod-facing) | Tables | Read/write from prod | Production agents, Batch Inferencing | Production agents |
| Prod Catalog (prod-facing) | Models | Read/write from prod | CI/CD promotion | Production agents |

---

## Extension Points for Further Development

Given this architecture, the following extension patterns are natural:

1. **Adding Agent 3**: Add "Agent 3 Tool & Function Library" and "Agent 3 Development" tasks to the Agent Development Workflow. Update Agent Router Development to include Agent 3 routing logic. Mirror the pattern in production (Agent 3 Deployment in App Deployment Workflow).

2. **Adding a new test type in Staging**: Add a new green-dashed box to the Staging workspace (e.g., "Load tests (CI)") connected to the MLflow Tracking Server via Test Logging.

3. **Adding a new data source**: Add a new job/task within the Data Preparation Workflow before "Chunking" to ingest and normalize the new source.

4. **Adding monitoring/alerting**: Extend the Production MLflow Tracking Server connections to trigger alerts when trace metrics fall below quality thresholds.

5. **Multi-account promotion**: The current design is single-account. To add a separate prod account, the Unity Catalog layer would split into separate account-level catalogs with cross-account sharing configured at the Lakehouse level.
