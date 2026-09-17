# FU Terminal v1.0.0

FU Terminal is a local-first terminal intelligence and safety engine. Version 1.0.0 establishes a deterministic-first architecture, centralized execution policy, evidence-backed diagnostics, independent verification, structured history, and local learning.

The installer uses `qwen2.5-coder:3b` as the default Ollama fallback model and pulls it automatically when Ollama is available. Model output remains a fallback and never bypasses FU's safety policy.

The release includes 54 passing regression checks, Linux/macOS platform validation, a man page, Docker packaging, GitHub Actions CI/container publishing, D2 architecture source, and a reproducible screenshot/narrated-demo pipeline.
