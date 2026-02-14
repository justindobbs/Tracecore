# FAQ: Why not X?

## Why not use an LLM judge?
Because judges reward explanations, not outcomes. If success can’t be checked mechanically, it doesn’t belong here.

## Why not benchmark reasoning quality?
Reasoning quality is not the deployment bottleneck. Operational failure modes are.

## Why not allow free-form natural language actions?
Free-form language hides capability boundaries. Actions should be explicit.

## Why not give shell access?
Unrestricted shell access encourages benchmark-specific hacks and makes failures uninterpretable.

## Why not use real external APIs?
They change, flake, and break determinism.

## Why not longer, more realistic tasks?
Long tasks hide failure modes. Short tasks surface them quickly.

## Why not optimize for efficiency scores?
Optimizing efficiency before correctness rewards fragile agents.

## Why not multi-agent tasks?
Single-agent reliability is not solved yet.

## How do I adapt OpenClaw agents?
Use the OpenClaw quickstart: `tutorials/openclaw_quickstart.md`.

## Why so opinionated?
Benchmarks without opinions collapse into demos. You’re free to fork it.
