# Overview

This document frames the opportunity for TraceCore to support `autoresearch`-style workflows while staying separate from the main runtime until the right abstraction is proven.

## Why this pairing is interesting

Karpathy's `autoresearch` has a simple loop:
- keep the editable surface tiny
- run bounded experiments
- optimize a measurable outcome
- iterate rapidly

TraceCore contributes complementary strengths:
- deterministic episode framing
- structured outcome taxonomy
- replayable artifacts
- evidence bundles and comparison workflows

Together, they suggest a model where autonomous research experiments become auditable, replayable, and easier to compare across agents or prompts.

## Integration options

### 1. Thin wrapper
Wrap `autoresearch` runs with TraceCore-style artifact capture.

Potential outputs:
- patch diff
- command invocation
- metric summary
- runtime identity
- termination/failure classification

This is the lowest-risk starting point.

### 2. Dedicated TraceCore task package
Recast the workflow as a constrained task:
- only `train.py` is writable
- training is time-bounded
- validator parses `val_bpb` and classifies the result

This is the best route if the goal is benchmarking research agents under a consistent contract.

### 3. Research orchestration substrate
Use TraceCore as the evidence and orchestration layer for branching experiment trees, promotion rules, and comparison dashboards.

This is higher leverage, but only after the wrapper path proves useful.

## Key open design questions

- What level of reproducibility is realistic for GPU training loops?
- Which artifact fields are required beyond TraceCore's current core envelope?
- Should optimization metrics remain task-specific validator outputs or become more standardized?
- Is the primary value benchmarking, research governance, or orchestration?

## Working assumption

The best initial approach is:
- preserve `autoresearch`'s minimalism
- add observability and evidence first
- delay contract changes until prototypes expose real requirements
- use a torch-free shim locally when GPU/torch aren't available (results are synthetic, but keep the loop exercisable)
