# Manual Verification Checklist
Use this script before publishing results or tagging a release to confirm that the CLI, run logging, trace viewer, and baseline diagnostics all behave as expected.

## 1. Prerequisites
- `python -m venv .venv && .venv\Scripts\activate` (or reuse an existing environment)
- `pip install -e .[dev]`
- Ensure `.agent_bench/runs/` exists (it is created automatically after the first run)
- Optional: `set PYTHONWARNINGS=default` so surfaced issues are visible during verification

## 2. CLI flow
1. Run a deterministic task twice to confirm persistence:
   ```powershell
   agent-bench run --agent agents/toy_agent.py --task filesystem_hidden_config@1 --seed 42
   agent-bench run --agent agents/rate_limit_agent.py --task rate_limited_api@1 --seed 11
   agent-bench run --agent agents/chain_agent.py --task rate_limited_chain@1 --seed 7
   ```
2. List recent artifacts and confirm the run IDs you just produced appear at the top:
   ```powershell
   agent-bench runs list --limit 5
   ```
3. Generate a baseline snapshot for each agent/task pair and sanity-check the metrics:
   ```powershell
   agent-bench baseline --agent agents/toy_agent.py --task filesystem_hidden_config@1
   agent-bench baseline --agent agents/rate_limit_agent.py --task rate_limited_api@1
   ```
4. Export a frozen baseline for the UI (create `.agent_bench/baselines/baseline-<ts>.json`):
   ```powershell
   agent-bench baseline --export latest
   ```
5. Note the `run_id` values—you’ll load them in the UI next.

## 3. Web UI flow
1. Start the server (module form avoids PATH issues):
   ```powershell
   python -m uvicorn agent_bench.webui.app:app --reload
   ```
2. Visit <http://localhost:8000> in a fresh browser tab.
3. Run the same agent/task combinations from the form and verify the result JSON matches the CLI output.
4. Click any “trace” link (or navigate to `/?trace_id=<run_id>#trace-viewer`) and confirm:
   - The Trace Viewer section auto-scrolls into view.
   - Step entries include observation, action, and result payloads.
   - The “Download JSON” link serves the `/api/traces/<run_id>` response.
5. Scroll to the Baselines panel and confirm it reflects the same success rate / averages seen in the CLI baseline output and shows the "Latest published" card referencing your export.
6. Run the `rate_limited_chain@1` task from the UI (or CLI) to verify the new pain task renders traces correctly—even if your reference agent fails, the trace + error should appear in the Trace tab.

## 4. Cleanup & determinism check
1. If you need a clean slate, delete artifacts after capturing them elsewhere:
   ```powershell
   Remove-Item -Recurse -Force .agent_bench\runs\*
   ```
2. Re-run the determinism suite to ensure no drift:
   ```powershell
   python -m pytest tests/test_determinism.py
   ```

## 5. Release gating
Before tagging or sharing results:
- Ensure this checklist has been completed in the current commit.
- Archive the `run_id` values referenced in reports so they remain a reproducible proof of behavior.
- Run the full test suite (`python -m pytest`).
- Note the harness version reported in run metadata; it should match the release tag.
