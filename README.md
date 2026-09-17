# FU Terminal

**Ubuntu-first terminal intelligence, diagnostics, safety, and learning — powered by deterministic retrieval with optional local AI.**

FU Terminal is a local-first command-line intelligence engine designed primarily for **Ubuntu Linux and Ubuntu-based systems**. It helps users discover commands, investigate system problems, understand Linux and Kubernetes environments, execute appropriate read-only operations safely, and verify whether an action actually achieved its intended result.

Unlike terminal assistants that send every request directly to a language model, FU uses a **retrieval-first architecture**:

**Curated FU Knowledge → TLDR → man/info → Commandlinefu → Local Ollama fallback**

This keeps common Linux and DevOps operations deterministic and explainable while still allowing a local language model to handle requests that cannot be resolved through trusted command sources.

FU is especially suited for Ubuntu Linux administration, DevOps engineering, Kubernetes troubleshooting, filesystem and storage diagnostics, command discovery, terminal learning, local AI workflows, evidence-based troubleshooting, safe command execution, home labs, and development environments.

## Why FU Terminal?

A command returning exit code `0` does not necessarily mean the user's actual problem was solved. FU therefore goes beyond command generation. Its architecture includes **investigation, evidence collection, execution history, safety policy, and post-execution verification**.

```text
User request
     │
     ▼
Deterministic retrieval
     ├── Curated FU knowledge
     ├── TLDR
     ├── man / info
     └── Commandlinefu
     │
     ▼
Command validation
     │
     ▼
FU Safety
     ├── Read-only → controlled execution
     ├── Write → approval required
     └── Dangerous / unknown → fail closed
     │
     ▼
Execution
     │
     ▼
Evidence + History + Verification
```

## Ubuntu-first

FU Terminal is currently developed and tested primarily around **Ubuntu Linux**, with Ubuntu 22.04-class environments forming the core development target.

Its Linux-focused capabilities include filesystem investigation, process and storage analysis, shell command retrieval, system evidence collection, Kubernetes diagnostics, Linux documentation retrieval, and safety-aware command execution.

Some components can operate on other platforms, but **Ubuntu is the primary supported platform for v1.x**. Platform-specific behavior should not be assumed to be identical on macOS or other Unix-like systems.

## Core capabilities

### Retrieval-first command resolution
FU searches deterministic and local command sources before falling back to an AI model.

### FU Safety
A centralized policy engine classifies commands and prevents AUTO mode or model output from bypassing destructive-command protections.

### FU Investigate
Read-only diagnostic workflows inspect the current state of the system before corrective actions are suggested.

### FU Evidence
Captures authoritative system signals that can be used for diagnosis and verification.

### FU Verify
Separates *command success* from *goal success* by checking current system state after execution.

### FU History & Incidents
Maintains execution records including requests, commands, sources, risk classification, return codes, timing, and logs.

### FU Learn
Provides command-line learning and practical Linux/DevOps guidance directly from the terminal.

### Kubernetes awareness
FU understands Kubernetes node conditions and is being expanded into a broader read-only Kubernetes investigation engine.

### Local Ollama fallback
AI fallback can remain on the local machine instead of requiring every terminal request to be sent to a cloud model.

## Design philosophy

> **Retrieve when possible. Reason when necessary. Verify what actually happened.**

The goal is not merely to generate shell commands. The goal is to make terminal work **safer, more explainable, more educational, and easier to verify**.
