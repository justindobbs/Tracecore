# TraceCore docs index

This page is the canonical documentation map for TraceCore: start here if you want the fastest path to installation, running your first deterministic episode, integrating TraceCore into CI, or exploring the spec and dashboard surfaces.

## Start with a goal

- **Install and run TraceCore locally**
  - [README quick example](../README.md#quick-example)
  - [Install TraceCore](../README.md#install-tracecore)
  - [Quick start commands](../README.md#quick-start-commands)
  - [CLI command reference](cli/commands.md)

- **Understand what TraceCore is**
  - [README overview](../README.md#what-is-tracecore)
  - [Technical spec explainer](specs/tracecore_spec.md)
  - [Architecture reference](reference/architecture.md)
  - [Project positioning](reference/project_positioning.md)

- **Integrate with an agent stack**
  - [OpenAI Agents Python guide](tutorials/openai_agents.md)
  - [AutoGen adapter tutorial](tutorials/autogen_adapter.md)
  - [LangChain adapter example](../examples/langchain_adapter/README.md)
  - [Agent catalog](agents/agents.md)
  - [Agent interface contract](agents/agent_interface.md)

- **Run TraceCore in CI or GitHub Actions**
  - [`tracecore-action`](https://github.com/justindobbs/tracecore-action)
  - [External consumer-validation repo](https://github.com/justindobbs/tracecore-action-test)
  - [CI workflow docs](ci/ci_workflows.md)

- **Inspect artifacts, bundles, and verification flows**
  - [Ledger workflow](ledger.md)
  - [Troubleshooting](cli/troubleshooting.md)
  - [Debugging playbook](operations/debugging_playbook.md)
  - [Manual verification checklist](operations/manual_verification.md)
  - [Artifact migration playbook](operations/artifact_migration_playbook.md)

## Core references

- **CLI and runtime**
  - [CLI command reference](cli/commands.md)
  - [CLI runner notes](cli/runner.md)
  - [CLI troubleshooting](cli/troubleshooting.md)
  - [Tool shim guidance](cli/tool_shim.md)

- **Specification**
  - [Canonical spec bundle](../agent_bench/spec/tracecore-spec-v1.0.md)
  - [Artifact schema](../agent_bench/spec/artifact-schema-v1.0.json)
  - [Determinism requirements](../agent_bench/spec/determinism.md)
  - [Compliance checklist](../agent_bench/spec/compliance-checklist-v0.1.md)
  - [Spec explainer](specs/tracecore_spec.md)

- **Agents and tasks**
  - [Agent catalog](agents/agents.md)
  - [Agent interface contract](agents/agent_interface.md)
  - [Task harness guide](tasks/task_harness.md)
  - [Task plugin contribution guide](tasks/plugin_contribution_guide.md)
  - [SPEC freeze / task registry snapshot](../SPEC_FREEZE.md)

- **Operations and governance**
  - [Release process](operations/release_process.md)
  - [Performance baselines](operations/performance_baselines.md)
  - [Record mode](operations/record_mode.md)
  - [Ledger governance](governance/ledger.md)
  - [Signing key rotation](governance/signing_key_rotation_guide.md)

## Recommended first examples

- **Fast deterministic local run**
  - `tracecore run pairing log_stream_monitor --seed 7 --strict-spec`

- **Fixture-backed adapter example**
  - [LangChain adapter example](../examples/langchain_adapter/README.md)

- **OpenAI Agents integration path**
  - [OpenAI Agents Python guide](tutorials/openai_agents.md)
  - [OpenAI Agents scaffold prompt](tutorials/openai_agents_scaffold_prompt.md)
