<div align="center">

<img src="docs/assets/foreman-hero.svg" alt="FOREMAN — Production Intelligence with Memory" width="100%">

*An AI platform that doesn't just monitor industrial production environments — it remembers them.*

![Status](https://img.shields.io/badge/status-active%20development-orange)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-TimescaleDB-336791?logo=postgresql&logoColor=white)
![MSIT](https://img.shields.io/badge/MSIT-AI--Track%20Capstone-6E40C9)
![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-lightgrey)

</div>

---

## What it is

Production lines generate data non-stop — sensor readings, PLC states, maintenance records, operator notes. Classic monitoring systems show the **current** state and raise an alarm when a threshold is crossed. What they lack is **memory**. They don't know that the same bearing temperature preceded a failure three weeks ago, or that a slow drift has been building for days.

**FOREMAN** closes that gap. It lays a reasoning layer with long-term memory over the production environment and answers questions that snapshots can't:

- *Which chain of events led to this failure?*
- *Is a process slowly drifting out of its normal range?*
- *When is this component likely to fail?*
- *Can the plant handle this planned extra load?*

The name says it all: a *foreman* is the experienced supervisor who has known the shop floor for years — and that institutional experience is exactly what FOREMAN provides as a system.

> **Context:** FOREMAN is the capstone project of the MSIT AI track. It combines 17 years of industrial background (workshop management, field service, PLC programming) with applied AI architecture.

---

## Architecture

Three cleanly decoupled layers. Industry delivers the data, FOREMAN reasons, operators act.

```mermaid
flowchart TB
    subgraph L1["① Industrial Environment"]
        direction LR
        SPS[PLC / OPC UA] 
        MQTT[MQTT / Modbus]
        LOGS[Logs & Maintenance History]
    end

    subgraph L2["② FOREMAN Reasoning Platform"]
        direction TB
        ING[Ingestion Service]
        subgraph R["Five Reasoners"]
            direction LR
            R1[Event-Chain\nReconstruction]
            R2[Drift\nDetection]
            R3[Failure\nPrediction]
            R4[Maintenance\nCycle Analysis]
            R5[Load\nSimulation]
        end
        GW[Model Gateway\nlocal + cloud]
    end

    subgraph L3["③ Output Channels"]
        direction LR
        DASH[Operator Dashboard]
        MCP[MCP Interface\nfor third-party systems]
    end

    MEM[(Memory Substrate\nexternal service)]

    L1 --> ING --> R
    R <--> GW
    R <--> MEM
    R --> DASH
    R --> MCP
```

### The five reasoners

| Reasoner | The question it answers | Method (high level) |
|---|---|---|
| **Event-Chain Reconstruction** | What led to this state? | Time-filtered recall + LLM synthesis |
| **Drift Detection** | Is something drifting slowly? | Statistical deviation monitoring |
| **Failure Prediction** | When will it fail? | Gradient boosting + LLM explanation |
| **Maintenance-Cycle Analysis** | Which maintenance actually helps? | Causal evaluation of past interventions |
| **Load Simulation** | Can the plant take this load? | Numerical simulation + Monte Carlo |

### The memory substrate

FOREMAN builds on an **external, biologically inspired memory substrate** that it consumes like a database. The substrate manages semantic events over time, consolidates recurring patterns, and monitors stability automatically. For FOREMAN it is a black-box dependency behind an HTTP API — the substrate code is **not** part of this repository.

---

## Tech stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12, FastAPI, async SQLAlchemy 2.0, Pydantic v2 |
| **Storage** | PostgreSQL + TimescaleDB (time series) + vector search |
| **Model gateway** | LiteLLM — local model (Qwen3 via Ollama) + cloud fallback (Anthropic) |
| **Frontend** | Next.js 15, Tailwind CSS, shadcn/ui, Recharts |
| **Industrial connectivity** | asyncua (OPC UA), paho-mqtt, pymodbus |
| **Integration** | Model Context Protocol (MCP) SDK |
| **Operations** | Docker Compose |

---

## Project structure

```
foreman/
├── README.md            ← you are here
├── GROUND_TRUTH.md      ← the specification (single source of truth)
├── docs/
│   └── WALKTHROUGH.md   ← plain-language explanation of every building block (German)
├── .env.example         ← configuration contract (no secrets)
└── .gitignore           ← protects secrets & the memory connection
```

> Code is added module by module. See **[GROUND_TRUTH.md](GROUND_TRUTH.md)** for the binding state and **[docs/WALKTHROUGH.md](docs/WALKTHROUGH.md)** for the plain-language explanation.

---

## Documentation principle

This project deliberately maintains **two** documents in parallel:

- **`GROUND_TRUTH.md`** — *the truth.* What holds: schema, routes, stack, conventions. Machine-near and concise.
- **`docs/WALKTHROUGH.md`** — *the explanation.* Why and how, in plain language. Per building block: what it does, where it sits in the architecture. *(Written in German — it is the author's defense companion for the code review.)*

Both are updated **in the same commit as the code** — so they cannot drift from reality.

---

## Engineering standards

This platform is built to defendable, reviewable standards — not vibe-coded.
Every change passes defined gates before it reaches `main`:

- **Type safety** — `mypy --strict` / `tsc --noEmit`, zero errors
- **Lint & complexity** — `ruff` / `eslint`, clean; cyclomatic-complexity gate
- **Tests** — `pytest`, ≥ 85 % coverage, a mandatory test block per feature
- **Security** — OWASP Web & LLM Top 10 (2025), secrets scan, dependency audit
- **Privacy by design** — GDPR Art. 25: worker data anonymized at the adapter layer
- **EU AI Act** — risk classification documented before code is written (Phase 0)
- **Living docs** — GROUND_TRUTH + WALKTHROUGH updated in the same commit, so
  documentation cannot drift from the code

See [`GROUND_TRUTH.md`](GROUND_TRUTH.md) §10 for the binding definition.

---

## Status

🚧 **Active development.** Foundation phase: skeleton, data ingestion, first end-to-end reasoner (drift). Roadmap and detailed state live in the GROUND_TRUTH.

---

## Author

**Patric Zeller** — AI architect · [patric-zeller.de](https://patric-zeller.de) · [GitHub](https://github.com/patricznr1)

---

<div align="center">
<sub>© 2026 Patric Zeller · All Rights Reserved · Showcase and educational repository, not licensed for reuse.</sub>
</div>
