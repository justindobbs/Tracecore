"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import metadata as _meta
from pathlib import Path

from agent_bench.config import AgentBenchConfig, ConfigError, load_config
from agent_bench.interactive import run_wizard
from agent_bench.pairings import find_pairing, list_pairings
from agent_bench.runner.baseline import (
    build_baselines,
    diff_runs,
    export_baseline,
    load_run_artifact,
)
from agent_bench.runner.bundle import verify_bundle, write_bundle
from agent_bench.runner.replay import check_record, check_replay, check_strict
from agent_bench.runner.failures import FAILURE_TYPES
from agent_bench.runner.runlog import list_runs, load_run, persist_run
from agent_bench.runner.runner import run
from agent_bench.tasks.registry import validate_registry_entries, validate_task_path
from agent_bench.webui.app import app
from agent_bench.maintainer import dumps_summary, maintain
from agent_bench.ledger import get_entry, list_entries
from agent_bench.session import latest_run_id as _latest_run_id
from agent_bench.session import load_session as _load_cli_session
from agent_bench.session import update_after_bundle as _session_after_bundle
from agent_bench.session import update_after_run as _session_after_run


STAR_NUDGE_SENTINEL = Path(".agent_bench") / ".star_prompt"


def _runtime_version() -> str:
    try:
        return _meta.version("tracecore")
    except _meta.PackageNotFoundError:
        try:
            return _meta.version("agent-bench")
        except _meta.PackageNotFoundError:
            return "0.0.0-dev"


def _maybe_print_star_nudge() -> None:
    """Emit a one-time reminder to star the repo after first use."""
    sentinel = STAR_NUDGE_SENTINEL
    if sentinel.exists():
        return

    _ = _runtime_version()  # warm cache / ensure pkg metadata installed

    print(
        "\n* Star us on GitHub: https://github.com/justindobbs/Tracecore\n",
        file=sys.stderr,
    )
    try:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.touch()
    except Exception:
        pass


def _load_config_from_args(config_path: str | None) -> AgentBenchConfig | None:
    try:
        return load_config(config_path)
    except ConfigError as exc:
        raise SystemExit(str(exc))


def _resolve_run_inputs(
    args: argparse.Namespace,
    config: AgentBenchConfig | None,
    *,
    require_seed: bool = True,
) -> tuple[str | None, str | None, int | None]:
    agent = getattr(args, "agent", None)
    task = getattr(args, "task", None)
    seed = getattr(args, "seed", None) if require_seed else None

    if config:
        agent = agent or config.get_default_agent()
        if task is None:
            task = config.get_task(agent=agent)
        if task is None:
            task = config.get_default_task()
        if require_seed and seed is None:
            seed = config.get_seed(agent=agent)
    return agent, task, seed


def _run_with_timeout(agent: str, task: str, seed: int, timeout: int | None) -> dict:
    """Run agent+task, enforcing a wall-clock timeout (seconds) if given."""
    if timeout is None:
        return run(agent, task, seed=seed)

    import threading
    result_box: list[dict] = []
    exc_box: list[BaseException] = []

    def _target() -> None:
        try:
            result_box.append(run(agent, task, seed=seed))
        except BaseException as exc:  # noqa: BLE001
            exc_box.append(exc)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise SystemExit(f"run timed out after {timeout}s (agent={agent}, task={task}, seed={seed})")
    if exc_box:
        raise exc_box[0]
    return result_box[0]


def _cmd_export(args: argparse.Namespace) -> int:
    from agent_bench.runner.export_otlp import export_otlp_json
    run_artifact = load_run_artifact(args.run)
    payload = export_otlp_json(run_artifact, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"OTLP export written: {out}", file=sys.stderr)
    else:
        print(payload)
    return 0


def _load_run_from_ref(ref: str) -> dict:
    """Load a run artifact either by run_id or explicit path."""
    return load_run_artifact(ref)


def _cmd_verify(args: argparse.Namespace) -> int:
    strict_spec: bool = getattr(args, "strict_spec", False)
    prefer_success: bool = getattr(args, "prefer_success", True)
    as_json: bool = getattr(args, "json", False)

    run_ref: str | None = getattr(args, "run", None)
    bundle_ref: str | None = getattr(args, "bundle", None)
    latest: bool = getattr(args, "latest", False)
    strict: bool = getattr(args, "strict", False)

    if latest or (run_ref is None and bundle_ref is None):
        resolved = _latest_run_id(prefer_success=prefer_success)
        if not resolved:
            payload = {"ok": False, "errors": ["no prior runs found to verify"]}
            if as_json:
                print(json.dumps(payload, indent=2))
            else:
                print("FAIL  no prior runs found to verify", file=sys.stderr)
            return 1
        run_ref = resolved

    run_artifact: dict | None = None
    bundle_dir: Path | None = None

    if run_ref:
        try:
            run_artifact = _load_run_from_ref(run_ref)
        except FileNotFoundError as exc:
            payload = {"ok": False, "errors": [str(exc)]}
            if as_json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"FAIL  {exc}", file=sys.stderr)
            return 1

    if bundle_ref:
        bundle_dir = Path(bundle_ref)
        if not bundle_dir.exists():
            payload = {"ok": False, "errors": [f"bundle directory not found: {bundle_dir}"]}
            if as_json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"FAIL  bundle directory not found: {bundle_dir}", file=sys.stderr)
            return 1
    else:
        session = _load_cli_session()
        if session and session.latest_bundle_dir:
            candidate = Path(session.latest_bundle_dir)
            if candidate.exists():
                bundle_dir = candidate

    errors: list[str] = []
    report: dict = {
        "ok": True,
        "run": run_artifact.get("run_id") if run_artifact else None,
        "bundle_dir": str(bundle_dir) if bundle_dir else None,
        "checks": {},
        "errors": errors,
    }

    if run_artifact is None and bundle_dir is None:
        errors.append("no run artifact or bundle supplied")
        report["ok"] = False

    if bundle_dir is not None:
        verify = verify_bundle(bundle_dir)
        report["checks"]["bundle_integrity"] = verify
        if not verify.get("ok"):
            report["ok"] = False
            for e in verify.get("errors", []):
                errors.append(f"bundle: {e}")

    if run_artifact is not None and strict_spec:
        from agent_bench.runner.spec_check import check_spec_compliance

        spec_report = check_spec_compliance(run_artifact)
        report["checks"]["strict_spec"] = spec_report
        if not spec_report.get("ok"):
            report["ok"] = False
            for e in spec_report.get("errors", []):
                errors.append(f"spec: {e}")

    if run_artifact is not None and bundle_dir is not None:
        checker = check_strict if strict else check_replay
        rr = checker(bundle_dir, run_artifact)
        report["checks"][rr.get("mode", "replay")] = rr
        if not rr.get("ok"):
            report["ok"] = False
            for e in rr.get("errors", []):
                errors.append(f"replay: {e}")

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        if report["ok"]:
            target = report.get("run") or "(no run_id)"
            print(f"OK  verify  run={target}", file=sys.stderr)
        else:
            print("FAIL  verify", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)

    return 0 if report["ok"] else 1


def _cmd_bundle_seal(args: argparse.Namespace) -> int:
    run_ref: str | None = getattr(args, "run", None)
    latest: bool = getattr(args, "latest", False)
    sign: bool = getattr(args, "sign", False)
    key: str | None = getattr(args, "key", None)
    fmt: str = getattr(args, "format", "text")

    if latest or run_ref is None:
        resolved = _latest_run_id(prefer_success=True)
        if not resolved:
            payload = {"ok": False, "errors": ["no successful prior runs found to seal"]}
            if fmt == "json":
                print(json.dumps(payload, indent=2))
            else:
                print("FAIL  no successful prior runs found to seal", file=sys.stderr)
            return 1
        run_ref = resolved

    try:
        run_artifact = _load_run_from_ref(run_ref)
    except FileNotFoundError as exc:
        payload = {"ok": False, "errors": [str(exc)]}
        if fmt == "json":
            print(json.dumps(payload, indent=2))
        else:
            print(f"FAIL  {exc}", file=sys.stderr)
        return 1

    bundle_dir = write_bundle(run_artifact)
    integrity = verify_bundle(bundle_dir)
    result: dict = {
        "ok": bool(integrity.get("ok")),
        "run_id": run_artifact.get("run_id"),
        "bundle_dir": str(bundle_dir),
        "verify": integrity,
    }

    if not integrity.get("ok"):
        result["ok"] = False

    if sign:
        from agent_bench.runner.bundle import sign_bundle

        sig = sign_bundle(bundle_dir, key_path=key)
        result["sign"] = sig
        if not sig.get("ok"):
            result["ok"] = False

    try:
        _session_after_bundle(bundle_dir=bundle_dir)
    except Exception:  # pragma: no cover
        pass

    if fmt == "json":
        print(json.dumps(result, indent=2))
    else:
        if result["ok"]:
            print(f"OK  sealed  {bundle_dir}")
        else:
            print(f"FAIL  sealed  {bundle_dir}")
            for err in integrity.get("errors", []):
                print(f"  - {err}")
            if sign and isinstance(result.get("sign"), dict):
                for err in result["sign"].get("errors", []):
                    print(f"  - {err}")

    return 0 if result["ok"] else 1


def _cmd_bundle_status(args: argparse.Namespace) -> int:
    fmt: str = getattr(args, "format", "text")
    limit: int = getattr(args, "limit", 10)

    root = Path(".agent_bench") / "baselines"
    bundles: list[dict] = []
    if root.exists():
        dirs = [p for p in root.iterdir() if p.is_dir()]
        dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for d in dirs[:limit]:
            verify = verify_bundle(d)
            signed = (d / "signature.json").exists()
            bundles.append({"bundle_dir": str(d), "ok": bool(verify.get("ok")), "signed": signed})

    if fmt == "json":
        print(json.dumps({"bundles": bundles}, indent=2))
        return 0

    if not bundles:
        print("No bundles found under .agent_bench/baselines", file=sys.stderr)
        return 0
    for b in bundles:
        status = "OK" if b.get("ok") else "FAIL"
        signed = "signed" if b.get("signed") else "unsigned"
        print(f"{status}  {signed}  {b.get('bundle_dir')}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    run_path_arg = getattr(args, "run", None)
    if run_path_arg:
        artifact_path = Path(run_path_arg)
        if not artifact_path.exists():
            print(f"Run artifact not found: {artifact_path}", file=sys.stderr)
            return 1
    else:
        runs_dir = Path(".agent_bench/runs")
        candidates = sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if runs_dir.exists() else []
        if not candidates:
            print("No run artifacts found (expected under .agent_bench/runs)", file=sys.stderr)
            return 1
        artifact_path = candidates[0]

    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Failed to read artifact {artifact_path}: {exc}", file=sys.stderr)
        return 1

    action_trace = artifact.get("action_trace") or []
    llm_traces = [entry.get("llm_trace") for entry in action_trace if entry.get("llm_trace")]

    print(f"Artifact: {artifact_path}")
    print(f"run_id:   {artifact.get('run_id', '?')}")
    print(f"task_ref: {artifact.get('task_ref', '?')}")
    print(f"agent:    {artifact.get('agent', '?')}")
    print(f"llm_trace entries: {len(llm_traces)}")
    if llm_traces:
        preview = llm_traces[0]
        print("first llm_trace entry:")
        print(json.dumps(preview, indent=2))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    config = getattr(args, "_config", None)
    timeout: int | None = getattr(args, "timeout", None)
    replay_bundle: str | None = getattr(args, "replay_bundle", None)
    strict: bool = getattr(args, "strict", False)
    strict_spec: bool = getattr(args, "strict_spec", False)
    record: bool = getattr(args, "record", False)
    from_config: str | None = getattr(args, "from_config", None)

    if from_config:
        from agent_bench.runner.episode_config import EpisodeConfig
        ep = EpisodeConfig.from_file(from_config)
        if not getattr(args, "agent", None):
            args.agent = ep.agent
        if not getattr(args, "task", None):
            args.task = ep.task_ref
        if getattr(args, "seed", None) is None:
            args.seed = ep.seed
        if ep.wall_clock_timeout_s is not None and timeout is None:
            timeout = ep.wall_clock_timeout_s

    if record and replay_bundle:
        raise SystemExit("--record and --replay-bundle are mutually exclusive")
    if record and strict:
        raise SystemExit("--record and --strict are mutually exclusive")

    if args.replay:
        artifact = load_run(args.replay)
        recorded_agent = artifact.get("agent")
        recorded_task = artifact.get("task_ref")
        recorded_seed = artifact.get("seed", 0)

        agent = args.agent or recorded_agent
        task = args.task or recorded_task
        seed = args.seed if args.seed is not None else recorded_seed

        if not agent or not task:
            raise SystemExit("replay requires an artifact with agent/task or explicit overrides")

        if agent != recorded_agent or task != recorded_task or seed != recorded_seed:
            print(
                "warning: overriding recorded artifact values for replay "
                f"(run_id={args.replay}, agent={recorded_agent}, task={recorded_task}, seed={recorded_seed})",
                file=sys.stderr,
            )
    elif replay_bundle:
        bundle_dir = Path(replay_bundle)
        if not bundle_dir.exists():
            raise SystemExit(f"bundle directory not found: {bundle_dir}")
        from agent_bench.runner.replay import load_bundle_manifest
        manifest = load_bundle_manifest(bundle_dir)
        agent = args.agent or manifest.get("agent")
        task = args.task or manifest.get("task_ref")
        seed = args.seed if args.seed is not None else manifest.get("seed", 0)
        if not agent or not task:
            raise SystemExit("--replay-bundle: bundle manifest missing agent/task_ref")
    else:
        agent, task, seed = _resolve_run_inputs(args, config)
        if not agent or not task:
            raise SystemExit(
                "agent and task are required unless using --replay or --replay-bundle "
                "(set CLI flags or defaults in agent-bench.toml)"
            )
        seed = 0 if seed is None else seed

    result = _run_with_timeout(agent, task, seed, timeout)
    try:
        persist_run(result)
    except Exception as exc:  # pragma: no cover - logging failure shouldn't abort run
        print(f"warning: failed to persist run artifact ({exc})", file=sys.stderr)

    try:
        _session_after_run(result=result)
    except Exception:  # pragma: no cover
        pass
    print(json.dumps(result, indent=2))
    _print_run_summary(result)
    _maybe_print_star_nudge()

    try:
        run_id = result.get("run_id")
        if isinstance(run_id, str) and run_id:
            print("\n[NEXT]", file=sys.stderr)
            print("  tracecore verify --latest", file=sys.stderr)
            print("  tracecore bundle seal --latest", file=sys.stderr)
            print(f"  tracecore dashboard   # trace: /?trace_id={run_id}", file=sys.stderr)
    except Exception:  # pragma: no cover
        pass

    if strict_spec:
        from agent_bench.runner.spec_check import check_spec_compliance
        spec_report = check_spec_compliance(result)
        if not spec_report["ok"]:
            print("\n[STRICT-SPEC FAILED]", file=sys.stderr)
            for err in spec_report["errors"]:
                print(f"  {err}", file=sys.stderr)
            return 1
        artifact_hash = result.get("artifact_hash", "")
        print(
            f"\n[STRICT-SPEC OK]  spec: {result.get('spec_version', '?')}  "
            f"artifact_hash: {artifact_hash}",
            file=sys.stderr,
        )

    if replay_bundle or strict:
        bundle_dir = Path(replay_bundle) if replay_bundle else None
        if bundle_dir is None:
            raise SystemExit("--strict requires --replay-bundle <path>")
        checker = check_strict if strict else check_replay
        report = checker(bundle_dir, result)
        if not report["ok"]:
            print(f"\n[{report['mode'].upper()} FAILED]", file=sys.stderr)
            for err in report["errors"]:
                print(f"  {err}", file=sys.stderr)
            return 1
        print(f"\n[{report['mode'].upper()} OK]", file=sys.stderr)

    if record:
        if not result.get("success"):
            print(
                "\n[RECORD REJECTED] run did not succeed — only successful runs can be sealed",
                file=sys.stderr,
            )
            return 1

        print("\n[RECORD] sealing bundle from first run…", file=sys.stderr)
        bundle_dir = write_bundle(result)
        print(f"[RECORD] bundle written: {bundle_dir}", file=sys.stderr)

        print("[RECORD] re-running to verify determinism…", file=sys.stderr)
        result2 = _run_with_timeout(agent, task, seed, timeout)
        try:
            persist_run(result2)
        except Exception as exc:  # pragma: no cover
            print(f"warning: failed to persist second run artifact ({exc})", file=sys.stderr)

        det_report = check_record(result, result2)
        if not det_report["ok"]:
            import shutil
            shutil.rmtree(bundle_dir, ignore_errors=True)
            print("\n[RECORD FAILED: NonDeterministic]", file=sys.stderr)
            for err in det_report["errors"]:
                print(f"  {err}", file=sys.stderr)
            print(f"[RECORD] bundle deleted: {bundle_dir}", file=sys.stderr)
            return 1

        print(f"\n[RECORD OK] bundle sealed: {bundle_dir}", file=sys.stderr)
        print(f"  commit with: git add {bundle_dir}", file=sys.stderr)

    return 0


def _print_run_summary(result: dict) -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        console = Console(stderr=True)
        success = result.get("failure_type") is None
        steps = result.get("steps_used", "?")
        tool_calls = result.get("tool_calls_used", "?")
        task_ref = result.get("task_ref", "?")
        failure_type = result.get("failure_type")
        failure_reason = result.get("failure_reason")
        if success:
            detail = f"[bold green]✓ SUCCESS[/bold green]  {task_ref}  |  steps: {steps}  tool_calls: {tool_calls}"
            console.print(Panel(detail, border_style="green"))
        else:
            ft = f"  failure_type: [yellow]{failure_type}[/yellow]" if failure_type else ""
            fr = f"\n  reason: [dim]{failure_reason}[/dim]" if failure_reason else ""
            detail = f"[bold red]✗ FAILED[/bold red]  {task_ref}  |  steps: {steps}  tool_calls: {tool_calls}{ft}{fr}"
            console.print(Panel(detail, border_style="red"))
    except Exception:
        pass


def _cmd_runs_list(args: argparse.Namespace) -> int:
    runs = list_runs(
        agent=args.agent,
        task_ref=args.task,
        limit=args.limit,
        failure_type=args.failure_type,
    )
    print(json.dumps(runs, indent=2))
    return 0


def _cmd_runs_summary(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table
    runs = list_runs(
        agent=args.agent,
        task_ref=args.task,
        limit=args.limit,
        failure_type=args.failure_type,
    )
    console = Console()
    if not runs:
        console.print("[dim]No runs found.[/dim]")
        return 0
    table = Table(box=None, padding=(0, 1), show_header=True)
    table.add_column("Outcome", no_wrap=True)
    table.add_column("Agent", style="bright_white", no_wrap=True)
    table.add_column("Task", style="magenta", no_wrap=True)
    table.add_column("Seed", style="dim", no_wrap=True)
    table.add_column("Steps", style="dim", no_wrap=True)
    table.add_column("Tool calls", style="dim", no_wrap=True)
    table.add_column("Run ID", style="dim", no_wrap=True)
    for r in runs:
        success = r.get("failure_type") is None
        outcome = "[green]✓ success[/green]" if success else f"[red]✗ {r.get('failure_type', 'failed')}[/red]"
        agent_short = r.get("agent", "").replace("agents/", "")
        table.add_row(
            outcome,
            agent_short,
            r.get("task_ref", ""),
            str(r.get("seed", "?")),
            str(r.get("steps_used", "?")),
            str(r.get("tool_calls_used", "?")),
            (r.get("run_id") or "")[:12],
        )
    console.print()
    console.print(table)
    console.print()
    return 0


def _compare_exit_code(diff: dict) -> int:
    summary = diff.get("summary", {})
    same_agent = bool(summary.get("same_agent"))
    same_task = bool(summary.get("same_task"))
    if not same_agent or not same_task:
        return 2
    if diff.get("step_diffs"):
        return 1
    if not summary.get("same_success"):
        return 1
    steps = summary.get("steps", {})
    tools = summary.get("tool_calls", {})
    if steps.get("run_a") != steps.get("run_b"):
        return 1
    if tools.get("run_a") != tools.get("run_b"):
        return 1
    return 0


def _print_diff_text(diff: dict, exit_code: int) -> None:
    summary = diff.get("summary", {})
    run_a = diff.get("run_a", {})
    run_b = diff.get("run_b", {})

    status = "identical"
    if exit_code == 2:
        status = "incompatible"
    elif exit_code == 1:
        status = "different"

    print(f"Compare: {status}")
    print(f"Agent A: {run_a.get('agent')}")
    print(f"Agent B: {run_b.get('agent')}")
    print(f"Task A: {run_a.get('task_ref')}")
    print(f"Task B: {run_b.get('task_ref')}")
    print(f"Success A: {run_a.get('success')}")
    print(f"Success B: {run_b.get('success')}")
    print(f"Steps A: {summary.get('steps', {}).get('run_a')}")
    print(f"Steps B: {summary.get('steps', {}).get('run_b')}")
    print(f"Tool calls A: {summary.get('tool_calls', {}).get('run_a')}")
    print(f"Tool calls B: {summary.get('tool_calls', {}).get('run_b')}")

    step_diffs = diff.get("step_diffs") or []
    if step_diffs:
        first = step_diffs[0]
        print(f"First divergence: step {first.get('step')}")


def _print_diff_pretty(diff: dict, exit_code: int, show_taxonomy: bool = False) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    summary = diff.get("summary", {})
    run_a = diff.get("run_a", {})
    run_b = diff.get("run_b", {})

    status_text = Text()
    if exit_code == 0:
        status_text.append("IDENTICAL", style="bold green")
    elif exit_code == 2:
        status_text.append("INCOMPATIBLE", style="bold red")
    else:
        status_text.append("DIFFERENT", style="bold yellow")

    console.print()
    console.print(Panel(status_text, title="Baseline Compare", border_style="cyan"))

    summary_table = Table(title="Run Summary", box=None, padding=(0, 2))
    summary_table.add_column("Property", style="cyan", no_wrap=True)
    summary_table.add_column("Baseline (A)", style="bright_white")
    summary_table.add_column("Current (B)", style="bright_white")
    summary_table.add_column("Match", justify="center")

    def _match_icon(same: bool) -> str:
        return "OK" if same else "NO"

    summary_table.add_row(
        "Agent",
        run_a.get("agent", ""),
        run_b.get("agent", ""),
        _match_icon(summary.get("same_agent", False)),
    )
    summary_table.add_row(
        "Task",
        run_a.get("task_ref", ""),
        run_b.get("task_ref", ""),
        _match_icon(summary.get("same_task", False)),
    )
    summary_table.add_row(
        "Success",
        str(run_a.get("success")),
        str(run_b.get("success")),
        _match_icon(summary.get("same_success", False)),
    )
    summary_table.add_row(
        "Seed",
        str(run_a.get("seed", "")),
        str(run_b.get("seed", "")),
        "",
    )

    console.print()
    console.print(summary_table)

    budget_table = Table(title="Budget Usage", box=None, padding=(0, 2))
    budget_table.add_column("Metric", style="cyan", no_wrap=True)
    budget_table.add_column("Baseline (A)", justify="right", style="bright_white")
    budget_table.add_column("Current (B)", justify="right", style="bright_white")
    budget_table.add_column("Delta (B - A)", justify="right")

    steps_a = summary.get("steps", {}).get("run_a", 0)
    steps_b = summary.get("steps", {}).get("run_b", 0)
    steps_delta = steps_b - steps_a
    steps_delta_str = f"{steps_delta:+d}" if steps_delta != 0 else "0"
    steps_delta_style = "red" if steps_delta > 0 else "green" if steps_delta < 0 else "dim"

    tools_a = summary.get("tool_calls", {}).get("run_a", 0)
    tools_b = summary.get("tool_calls", {}).get("run_b", 0)
    tools_delta = tools_b - tools_a
    tools_delta_str = f"{tools_delta:+d}" if tools_delta != 0 else "0"
    tools_delta_style = "red" if tools_delta > 0 else "green" if tools_delta < 0 else "dim"

    budget_table.add_row(
        "Steps",
        str(steps_a),
        str(steps_b),
        Text(steps_delta_str, style=steps_delta_style),
    )
    budget_table.add_row(
        "Tool calls",
        str(tools_a),
        str(tools_b),
        Text(tools_delta_str, style=tools_delta_style),
    )

    console.print()
    console.print(budget_table)

    if show_taxonomy:
        failure_a = run_a.get("failure_type")
        failure_b = run_b.get("failure_type")
        if failure_a or failure_b:
            tax_table = Table(title="Failure Taxonomy", box=None, padding=(0, 2))
            tax_table.add_column("Run", style="cyan")
            tax_table.add_column("Failure Type", style="bright_white")
            tax_table.add_column("Termination Reason", style="dim")
            tax_table.add_row(
                "Baseline (A)",
                failure_a or "—",
                run_a.get("termination_reason", "—"),
            )
            tax_table.add_row(
                "Current (B)",
                failure_b or "—",
                run_b.get("termination_reason", "—"),
            )
            console.print()
            console.print(tax_table)

    step_diffs = diff.get("step_diffs") or []
    if step_diffs:
        console.print()
        console.print(f"[bold yellow]Trace Divergence:[/bold yellow] {len(step_diffs)} step(s) differ")
        console.print()

        diff_table = Table(title="Per-Step Differences (first 5)", box=None, padding=(0, 1))
        diff_table.add_column("Step", justify="right", style="cyan", no_wrap=True)
        diff_table.add_column("Baseline Action", style="bright_white")
        diff_table.add_column("Current Action", style="bright_white")

        for step_diff in step_diffs[:5]:
            step_num = step_diff.get("step", "?")
            entry_a = step_diff.get("run_a") or {}
            entry_b = step_diff.get("run_b") or {}

            action_a = entry_a.get("action", {})
            action_b = entry_b.get("action", {})

            action_a_str = action_a.get("type", "—") if action_a else "—"
            action_b_str = action_b.get("type", "—") if action_b else "—"

            diff_table.add_row(str(step_num), action_a_str, action_b_str)

        console.print(diff_table)

        if len(step_diffs) > 5:
            console.print(f"[dim]... and {len(step_diffs) - 5} more step(s)[/dim]")

    console.print()


def _cmd_baseline(args: argparse.Namespace) -> int:
    config = getattr(args, "_config", None)
    verify_target = getattr(args, "verify", None)
    if verify_target:
        bundle_path = Path(verify_target)
        report = verify_bundle(bundle_path)
        payload = {"bundle_dir": str(bundle_path), "verify": report}
        print(json.dumps(payload, indent=2))
        return 0 if report.get("ok") else 1
    compare = getattr(args, "compare", None)
    if compare:
        try:
            run_a = load_run_artifact(compare[0])
            run_b = load_run_artifact(compare[1])
        except FileNotFoundError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1
        diff = diff_runs(run_a, run_b)
        exit_code = _compare_exit_code(diff)
        show_taxonomy = getattr(args, "show_taxonomy", False)
        if args.format == "text":
            _print_diff_text(diff, exit_code)
        elif args.format == "pretty":
            _print_diff_pretty(diff, exit_code, show_taxonomy=show_taxonomy)
        else:
            print(json.dumps(diff, indent=2))
        return exit_code
    agent, task, _ = _resolve_run_inputs(args, config, require_seed=False)
    rows = build_baselines(agent=agent, task_ref=task, max_runs=args.limit)
    payload: object = rows
    if args.export is not None:
        target = None if args.export == "" else args.export
        meta = {
            "agent_filter": agent,
            "task_filter": task,
            "limit": args.limit,
        }
        path = export_baseline(rows, path=target, metadata=meta)
        payload = {"rows": rows, "export_path": str(path)}
    if getattr(args, "bundle", False):
        from agent_bench.runner.runlog import iter_runs
        matching = list(iter_runs(agent=agent, task_ref=task))
        if not matching:
            print(json.dumps({"error": "no matching runs found to bundle"}, indent=2), file=sys.stderr)
            return 1
        most_recent = matching[0]
        bundle_dir = write_bundle(most_recent)
        report = verify_bundle(bundle_dir)
        payload = {"bundle_dir": str(bundle_dir), "run_id": most_recent.get("run_id"), "verify": report}
        print(json.dumps(payload, indent=2))
        return 0 if report.get("ok") else 1
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    """Top-level `tracecore diff run_a run_b` command."""
    import time as _time
    t0 = _time.monotonic()
    try:
        run_a = load_run_artifact(args.run_a)
        run_b = load_run_artifact(args.run_b)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    diff = diff_runs(run_a, run_b)
    elapsed = _time.monotonic() - t0
    exit_code = _compare_exit_code(diff)

    fmt = getattr(args, "format", "pretty")
    if fmt == "json":
        diff["_elapsed_s"] = round(elapsed, 3)
        print(json.dumps(diff, indent=2))
    elif fmt == "otlp":
        from agent_bench.runner.export_otlp import run_to_otlp
        payload = {
            "diff_elapsed_s": round(elapsed, 3),
            "run_a": run_to_otlp(run_a),
            "run_b": run_to_otlp(run_b),
            "taxonomy": diff.get("taxonomy"),
            "budget_delta": diff.get("budget_delta"),
        }
        print(json.dumps(payload, indent=2))
    elif fmt == "text":
        _print_diff_text(diff, exit_code)
        print(f"elapsed: {elapsed:.3f}s")
    else:
        _print_diff_pretty(diff, exit_code, show_taxonomy=True)

    return exit_code


def _cmd_bundle_sign(args: argparse.Namespace) -> int:
    from agent_bench.runner.bundle import sign_bundle
    bundle_dir = Path(args.path)
    if not bundle_dir.exists():
        print(f"Bundle directory not found: {bundle_dir}", file=sys.stderr)
        return 1
    result = sign_bundle(bundle_dir, key_path=getattr(args, "key", None))
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        if result.get("ok"):
            print(f"Signed  {bundle_dir}")
            print(f"  signature: {result.get('signature_file')}")
        else:
            print(f"FAIL  {bundle_dir}")
            for err in result.get("errors", []):
                print(f"  - {err}")
    return 0 if result.get("ok") else 1


def _cmd_bundle_verify(args: argparse.Namespace) -> int:
    bundle_dir = Path(args.path)
    if not bundle_dir.exists():
        print(f"Bundle directory not found: {bundle_dir}", file=sys.stderr)
        return 1
    report = verify_bundle(bundle_dir)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        if report["ok"]:
            print(f"OK  {bundle_dir}")
        else:
            print(f"FAIL  {bundle_dir}")
            for err in report["errors"]:
                print(f"  - {err}")
    return 0 if report["ok"] else 1


def _cmd_run_pairing(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table
    console = Console()

    if getattr(args, "list", False):
        table = Table(title="Known Pairings", box=None, padding=(0, 1))
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Agent", style="bright_white", no_wrap=True)
        table.add_column("Task", style="magenta", no_wrap=True)
        table.add_column("Description", style="green")
        for p in list_pairings():
            table.add_row(p.name, p.agent, p.task, p.description)
        console.print()
        console.print(table)
        console.print()
        return 0

    if getattr(args, "all", False):
        return _cmd_run_pairing_all(args)

    name = getattr(args, "pairing_name", None)
    pairing = find_pairing(name, cwd=Path.cwd())

    if pairing is None:
        console.print("[bold red]No pairing found.[/bold red]")
        if name:
            console.print(f"  '[yellow]{name}[/yellow]' does not match any known pairing.")
        else:
            console.print(
                "  Navigate to a directory containing a paired agent file, or specify a name:\n"
                "  [cyan]agent-bench run pairing log_stream_monitor[/cyan]\n"
                "  Run [cyan]agent-bench run pairing --list[/cyan] to see all available pairings."
            )
        return 1

    seed = args.seed if args.seed is not None else 0
    console.print(f"[dim]Pairing:[/dim] [cyan]{pairing.name}[/cyan]  "
                  f"[dim]agent:[/dim] {pairing.agent}  "
                  f"[dim]task:[/dim] {pairing.task}  "
                  f"[dim]seed:[/dim] {seed}")
    run_args = argparse.Namespace(
        agent=pairing.agent,
        task=pairing.task,
        seed=seed,
        replay=None,
        timeout=getattr(args, "timeout", None),
        _config=getattr(args, "_config", None),
    )
    return _cmd_run(run_args)


def _cmd_run_pairing_all(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table
    console = Console()
    seed = args.seed if args.seed is not None else 0
    timeout: int | None = getattr(args, "timeout", None)
    pairings = list_pairings()

    console.print(f"\n[bold]Running {len(pairings)} pairings[/bold]  seed={seed}\n")

    rows: list[tuple] = []
    any_failed = False
    for p in pairings:
        console.print(f"  [dim]→[/dim] [cyan]{p.name}[/cyan]  {p.agent}  {p.task} ...", end="")
        try:
            result = _run_with_timeout(p.agent, p.task, seed, timeout)
            try:
                persist_run(result)
            except Exception:  # pragma: no cover
                pass
            success = result.get("failure_type") is None
            outcome = "[green]✓ success[/green]" if success else f"[red]✗ {result.get('failure_type', 'failed')}[/red]"
            rows.append((
                outcome,
                p.name,
                str(result.get("steps_used", "?")),
                str(result.get("tool_calls_used", "?")),
                result.get("failure_reason") or "",
            ))
            if not success:
                any_failed = True
        except SystemExit as exc:
            rows.append(("[red]✗ timeout[/red]", p.name, "—", "—", str(exc)))
            any_failed = True
        except Exception as exc:  # noqa: BLE001
            rows.append(("[red]✗ error[/red]", p.name, "—", "—", str(exc)))
            any_failed = True
        console.print(" " + rows[-1][0])

    table = Table(title="Pairing Smoke-Test Results", box=None, padding=(0, 1))
    table.add_column("Outcome", no_wrap=True)
    table.add_column("Pairing", style="cyan", no_wrap=True)
    table.add_column("Steps", style="dim", no_wrap=True)
    table.add_column("Tool calls", style="dim", no_wrap=True)
    table.add_column("Note", style="dim")
    for row in rows:
        table.add_row(*row)
    console.print()
    console.print(table)
    console.print()
    return 1 if any_failed else 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    import uvicorn

    app_target = "agent_bench.webui.app:app" if args.reload else app
    uvicorn.run(app_target, host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_interactive(args: argparse.Namespace) -> int:
    config = getattr(args, "_config", None)
    selection = run_wizard(
        config=config,
        no_color=args.no_color,
        save_session=args.save_session,
        include_plugins=args.plugins,
        dry_run=args.dry_run,
    )
    if selection is None:
        return 0 if args.dry_run else 1
    agent, task, seed = selection
    run_args = argparse.Namespace(
        agent=agent,
        task=task,
        seed=seed,
        replay=None,
        _config=config,
    )
    return _cmd_run(run_args)


def _cmd_tasks_lint(args: argparse.Namespace) -> int:
    """Extended plugin contract linting: action_schema, budgets, sandbox, versioning."""
    import importlib.util

    from agent_bench.tasks.registry import validate_task_path, list_task_descriptors

    errors: list[dict] = []
    warnings: list[dict] = []

    def _lint_task_dir(path: Path) -> None:
        label = str(path)

        path_errors = validate_task_path(path)
        for e in path_errors:
            errors.append({"path": label, "rule": "manifest", "message": e})

        actions_path = path / "actions.py"
        if actions_path.exists():
            spec = importlib.util.spec_from_file_location("_lint_actions", actions_path)
            try:
                mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                if not hasattr(mod, "action_schema"):
                    warnings.append({
                        "path": label,
                        "rule": "action_schema",
                        "message": "actions.py is missing action_schema() — required for test_action_contracts",
                    })
                if not hasattr(mod, "execute"):
                    errors.append({
                        "path": label,
                        "rule": "execute",
                        "message": "actions.py is missing execute(action) function",
                    })
            except Exception as exc:
                errors.append({"path": label, "rule": "import", "message": f"actions.py failed to import: {exc}"})
        else:
            errors.append({"path": label, "rule": "actions_missing", "message": "actions.py not found"})

        manifest_candidates = [path / "task.toml", path / "task.yaml", path / "manifest.json"]
        manifest_found = any(p.exists() for p in manifest_candidates)
        if not manifest_found:
            errors.append({"path": label, "rule": "manifest_missing", "message": "No task.toml / task.yaml / manifest.json found"})

    paths = getattr(args, "path", None) or []
    if paths:
        for raw_path in paths:
            _lint_task_dir(Path(raw_path))
    else:
        try:
            descriptors = list_task_descriptors()
        except Exception as exc:
            print(json.dumps({"errors": [str(exc)], "warnings": [], "ok": False}, indent=2))
            return 1
        for descriptor in descriptors:
            if descriptor.path:
                _lint_task_dir(descriptor.path)

    ok = len(errors) == 0
    payload = {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "summary": f"{len(errors)} error(s), {len(warnings)} warning(s)",
    }

    fmt = getattr(args, "format", "text")
    if fmt == "json":
        print(json.dumps(payload, indent=2))
    else:
        if ok and not warnings:
            print(f"OK  {payload['summary']}")
        else:
            for e in errors:
                print(f"ERROR  [{e['rule']}]  {e['path']}: {e['message']}")
            for w in warnings:
                print(f"WARN   [{w['rule']}]  {w['path']}: {w['message']}")
            print(payload["summary"])

    return 0 if ok else 1


def _cmd_tasks_validate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    paths = getattr(args, "path", None) or []
    if not paths and not args.registry:
        args.registry = True

    for raw_path in paths:
        path = Path(raw_path)
        path_errors = validate_task_path(path)
        if path_errors:
            for err in path_errors:
                errors.append(f"{path}: {err}")

    if args.registry:
        errors.extend(validate_registry_entries())

    payload = {"valid": not errors, "errors": errors}
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 1


def _cmd_new_agent(args: argparse.Namespace) -> int:
    from rich.console import Console
    console = Console()

    raw_name: str = args.name
    class_name = "".join(part.capitalize() for part in raw_name.replace("-", "_").split("_")) + "Agent"
    file_name = raw_name.replace("-", "_") + "_agent.py"
    output_dir = Path(args.output_dir) if args.output_dir else Path("agents")
    target = output_dir / file_name

    if target.exists() and not args.force:
        console.print(f"[bold red]Error:[/bold red] {target} already exists. Use [cyan]--force[/cyan] to overwrite.")
        return 1

    stub = f'''"""Agent stub generated by `agent-bench new-agent {raw_name}`."""

from __future__ import annotations


class {class_name}:
    """Stub agent implementing the reset / observe / act interface.

    Replace the placeholder logic in `act()` with your agent's decision loop.
    """

    def __init__(self) -> None:
        self.reset({{}})

    def reset(self, task_spec) -> None:
        """Called once before each episode. Store task_spec for later use."""
        self.task_spec = task_spec or {{}}
        self.obs = None
        self.step = 0

    def observe(self, observation) -> None:
        """Receive the latest environment observation."""
        self.obs = observation

    def act(self) -> dict:
        """Return the next action dict.

        Every action must have at minimum:
            {{"type": "<action_type>", "args": {{...}}}}

        Use {{"type": "set_output", "args": {{"key": ..., "value": ...}}}} to
        submit the final answer and end the episode successfully.

        Use {{"type": "wait", "args": {{}}}} to consume a step without acting.
        """
        self.step += 1

        if self.obs is None:
            return {{"type": "wait", "args": {{}}}}

        remaining_steps = self.obs.get("remaining_steps", 0)
        remaining_tool_calls = self.obs.get("remaining_tool_calls", 0)

        if remaining_steps <= 1 or remaining_tool_calls <= 1:
            return {{"type": "wait", "args": {{}}}}

        # TODO: implement your agent logic here
        return {{"type": "wait", "args": {{}}}}
'''

    output_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(stub, encoding="utf-8")
    console.print(f"[green]Created[/green] {target}")
    console.print(f"  Class:  [cyan]{class_name}[/cyan]")
    console.print(f"  Run it: [dim]agent-bench run --agent {target} --task <task_ref> --seed 0[/dim]")
    return 0


def _cmd_openclaw(args: argparse.Namespace) -> int:
    from rich.console import Console
    from agent_bench.openclaw import (
        detect_openclaw_agent,
        scaffold_openclaw_adapter,
        scaffold_gateway_adapter,
    )

    console = Console(stderr=True)
    cwd = Path.cwd()
    agent_id: str | None = getattr(args, "agent_id", None)
    gateway: bool = getattr(args, "gateway", False)

    meta = detect_openclaw_agent(cwd, agent_id)
    if meta is None:
        console.print("[bold red]Error:[/bold red] No OpenClaw agent found.")
        if agent_id:
            console.print(f"  Agent '[yellow]{agent_id}[/yellow]' not in openclaw.json.")
        else:
            console.print(
                "  No openclaw.json found in CWD or ~/.openclaw/. "
                "Navigate to your OpenClaw workspace or pass [cyan]--agent-id <id>[/cyan]."
            )
        return 1

    console.print(f"[dim]Detected OpenClaw agent:[/dim] [cyan]{meta['id']}[/cyan]")
    if meta.get("prompt_file"):
        console.print(f"  Prompt file: [dim]{meta['prompt_file']}[/dim]")
    if (meta.get("model") or {}).get("primary"):
        console.print(f"  Model: [dim]{meta['model']['primary']}[/dim]")

    config_dir = Path(meta["config_path"]).parent
    out_dir = config_dir / "tracecore_adapters"
    adapter_path = out_dir / f"{meta['id']}_adapter_agent.py"

    if not adapter_path.exists():
        adapter_path = scaffold_openclaw_adapter(meta, out_dir)
        console.print(f"[green]Scaffolded[/green] {adapter_path}")
        if gateway:
            gw_path = scaffold_gateway_adapter(meta, out_dir)
            console.print(f"[green]Scaffolded[/green] {gw_path} [dim](gateway)[/dim]")
        console.print(
            f"  Edit [cyan]tracecore_adapters/{adapter_path.name}[/cyan] then re-run "
            "[dim]agent-bench openclaw[/dim] to test."
        )
        return 0

    task_ref: str = getattr(args, "task", None) or "filesystem_hidden_config@1"
    seed: int = getattr(args, "seed", None) or 0
    console.print(
        f"[dim]Running:[/dim] {adapter_path.name}  "
        f"[dim]task:[/dim] {task_ref}  [dim]seed:[/dim] {seed}"
    )
    run_args = argparse.Namespace(
        agent=str(adapter_path),
        task=task_ref,
        seed=seed,
        replay=None,
        timeout=getattr(args, "timeout", None),
        _config=getattr(args, "_config", None),
    )
    return _cmd_run(run_args)


def _cmd_openclaw_export(args: argparse.Namespace) -> int:
    from rich.console import Console
    from agent_bench.openclaw import (
        detect_openclaw_agent,
        export_openclaw_agent,
    )

    console = Console(stderr=True)
    cwd = Path.cwd()
    agent_id: str | None = getattr(args, "agent_id", None)
    meta = detect_openclaw_agent(cwd, agent_id)
    if meta is None:
        console.print("[bold red]Error:[/bold red] No OpenClaw agent found. Run [cyan]agent-bench openclaw[/cyan] first.")
        return 1

    config_dir = Path(meta["config_path"]).parent
    out_dir_arg = getattr(args, "out_dir", None)
    if out_dir_arg:
        out_dir = Path(out_dir_arg).resolve()
    else:
        out_dir = config_dir / "tracecore_export"

    adapter_path = config_dir / "tracecore_adapters" / f"{meta['id']}_adapter_agent.py"
    if not adapter_path.exists():
        console.print(f"[bold red]Error:[/bold red] Adapter not found: {adapter_path}")
        console.print("  Run [cyan]agent-bench openclaw[/cyan] to scaffold and test it first.")
        return 1

    last_runs = list_runs(agent=str(adapter_path), limit=1)
    passing = [r for r in last_runs if r.get("failure_type") is None]
    if not passing:
        console.print("[bold red]Error:[/bold red] No passing run found for this adapter.")
        console.print(
            "  Test it first: [cyan]agent-bench openclaw "
            f"--agent-id {meta['id']}[/cyan]"
        )
        return 1

    last_run = passing[0]

    gw_path = config_dir / "tracecore_adapters" / f"{meta['id']}_gateway_adapter_agent.py"
    if not gw_path.exists():
        gw_path = None

    bundle_dir = export_openclaw_agent(
        agent_meta=meta,
        adapter_path=adapter_path,
        last_run=last_run,
        out_dir=out_dir,
        gateway_adapter_path=gw_path,
    )
    console.print(f"[green]Exported[/green] {bundle_dir}")
    console.print(f"  Run ID: [dim]{last_run.get('run_id', '?')}[/dim]")
    console.print(f"  Task:   [dim]{last_run.get('task_ref', '?')}[/dim]")
    return 0


def _cmd_ledger(args: argparse.Namespace) -> int:
    show = getattr(args, "show", None)
    if show:
        entry = get_entry(show)
        if entry is None:
            print(f"No ledger entry found for {show!r}", file=sys.stderr)
            return 1
        print(json.dumps(entry, indent=2))
        return 0
    entries = list_entries()
    if not entries:
        print("Ledger is empty.", file=sys.stderr)
        return 0
    for entry in entries:
        tasks = entry.get("tasks", [])
        task_summary = ", ".join(t["task_ref"] for t in tasks)
        print(f"{entry['agent']}  [{entry.get('suite', '?')}]  {task_summary}")
    return 0


def _cmd_ledger_verify(args: argparse.Namespace) -> int:
    from agent_bench.ledger import get_entry
    from agent_bench.ledger.signing import (
        load_public_key_from_file,
        verify_bundle_signature,
        verify_registry_signature,
    )

    try:
        pub_key = load_public_key_from_file()
    except Exception as exc:
        print(f"[ERROR] Failed to load public key: {exc}", file=sys.stderr)
        return 1

    bundle_path = getattr(args, "bundle", None)
    entry_stem = getattr(args, "entry", None)
    verify_reg = getattr(args, "registry", False)

    if verify_reg:
        from agent_bench.ledger import _load_registry
        registry = _load_registry()
        ok = verify_registry_signature(registry, pub_key)
        status = "[OK]" if ok else "[FAIL]"
        print(f"{status} Registry signature verification")
        if not ok:
            sig = registry.get("ledger_signature")
            if not sig:
                print("  ledger_signature field missing — registry has not been signed yet.", file=sys.stderr)
            return 1
        signed_at = registry.get("signed_at", "?")
        pubkey_id = registry.get("signing_pubkey_id", "?")
        print(f"  signed_at:        {signed_at}")
        print(f"  signing_pubkey_id: {pubkey_id}")
        return 0

    if bundle_path:
        bundle_dir = Path(bundle_path).resolve()
        if not bundle_dir.exists():
            print(f"[ERROR] Bundle directory not found: {bundle_dir}", file=sys.stderr)
            return 1
        sig = None
        sha256 = None
        if entry_stem:
            entry = get_entry(entry_stem)
            if entry:
                for task_row in entry.get("tasks", []):
                    if task_row.get("bundle_sha256") and task_row.get("bundle_signature"):
                        sha256 = task_row["bundle_sha256"]
                        sig = task_row["bundle_signature"]
                        break
        if not sig or not sha256:
            try:
                import json
                manifest = json.loads((bundle_dir / "manifest.json").read_text())
                sha256 = manifest.get("bundle_sha256")
                sig = manifest.get("bundle_signature")
            except Exception:
                pass
        if not sig or not sha256:
            print("[ERROR] No bundle_sha256/bundle_signature found — bundle has not been signed.", file=sys.stderr)
            return 1
        ok = verify_bundle_signature(bundle_dir, sig, sha256, pub_key)
        status = "[OK]" if ok else "[FAIL]"
        print(f"{status} Bundle signature verification: {bundle_dir}")
        return 0 if ok else 1

    if entry_stem:
        entry = get_entry(entry_stem)
        if entry is None:
            print(f"[ERROR] No ledger entry found for {entry_stem!r}", file=sys.stderr)
            return 1
        any_signed = False
        all_ok = True
        for task_row in entry.get("tasks", []):
            sha256 = task_row.get("bundle_sha256")
            sig = task_row.get("bundle_signature")
            task_ref = task_row.get("task_ref", "?")
            run_id = task_row.get("run_artifact")
            if not sha256 or not sig:
                print(f"  [-] {task_ref}: not signed")
                continue
            bundle_dir = Path(".agent_bench") / "baselines" / run_id if run_id else None
            if bundle_dir and bundle_dir.exists():
                ok = verify_bundle_signature(bundle_dir, sig, sha256, pub_key)
                status = "[OK]" if ok else "[FAIL]"
                if not ok:
                    all_ok = False
            else:
                ok = True
                status = "[OK-hash-only]"
            any_signed = True
            signed_at = task_row.get("signed_at", "?")
            print(f"  {status} {task_ref}  (signed_at={signed_at})")
        if not any_signed:
            print(f"No signed task rows for {entry_stem!r} — entry has not been signed.", file=sys.stderr)
            return 1
        return 0 if all_ok else 1

    print("Specify --bundle <dir>, --entry <agent>, or --registry.", file=sys.stderr)
    return 1


def _cmd_run_batch(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table
    from agent_bench.runner.batch import BatchJob, run_batch

    console = Console()
    batch_file: str | None = getattr(args, "batch_file", None)
    workers: int | None = getattr(args, "workers", None)
    timeout: int | None = getattr(args, "timeout", None)
    strict_spec: bool = getattr(args, "strict_spec", False)

    if batch_file:
        batch_path = Path(batch_file)
        if not batch_path.exists():
            console.print(f"[bold red]Error:[/bold red] batch file not found: {batch_path}")
            return 1
        with batch_path.open(encoding="utf-8") as fh:
            raw_jobs = json.load(fh)
        if not isinstance(raw_jobs, list):
            console.print("[bold red]Error:[/bold red] batch file must be a JSON array of job objects")
            return 1
        jobs = [
            BatchJob(
                agent=j["agent"],
                task_ref=j["task_ref"],
                seed=j.get("seed", 0),
                timeout=j.get("timeout"),
            )
            for j in raw_jobs
        ]
    else:
        from agent_bench.pairings import list_pairings
        pairings = list_pairings()
        seed = getattr(args, "seed", None) or 0
        jobs = [BatchJob(agent=p.agent, task_ref=p.task, seed=seed) for p in pairings]

    if not jobs:
        console.print("[yellow]No jobs to run.[/yellow]")
        return 0

    console.print(f"\n[bold]Batch run[/bold]  jobs={len(jobs)}  workers={workers or 'auto'}  "
                  f"timeout={timeout or 'none'}  strict-spec={strict_spec}\n")

    report = run_batch(jobs, workers=workers, timeout=timeout, strict_spec=strict_spec)
    results = report["results"]
    summary = report["summary"]

    table = Table(title="Batch Results", box=None, padding=(0, 1))
    table.add_column("Outcome", no_wrap=True)
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Task", style="magenta", no_wrap=True)
    table.add_column("Seed", style="dim", no_wrap=True)
    table.add_column("Wall (s)", style="dim", justify="right", no_wrap=True)
    table.add_column("Note", style="dim")

    for br in results:
        outcome = "[green]✓ pass[/green]" if br.success else "[red]✗ fail[/red]"
        note = br.error or ""
        if br.result and not br.success:
            note = note or (br.result.get("failure_type") or "")
        table.add_row(
            outcome,
            br.job.agent,
            br.job.task_ref,
            str(br.job.seed),
            f"{br.wall_clock_s:.1f}",
            note,
        )

    console.print(table)
    console.print()
    console.print(
        f"[bold]Summary[/bold]  passed={summary['passed']}  failed={summary['failed']}  "
        f"p50={summary['p50_wall_clock_s']}s  p95={summary['p95_wall_clock_s']}s"
    )
    console.print()
    return 0 if report["ok"] else 1


def _cmd_runs_metrics(args: argparse.Namespace) -> int:
    from agent_bench.runner.metrics import compute_all_metrics, compute_metrics

    task_ref: str | None = getattr(args, "task", None)
    agent: str | None = getattr(args, "agent", None)
    limit: int = getattr(args, "limit", 500)
    fmt: str = getattr(args, "format", "json")

    if task_ref or agent:
        data = compute_metrics(task_ref=task_ref, agent=agent, limit=limit)
        payload = data
    else:
        data = compute_all_metrics(limit=limit)
        payload = data

    if fmt == "json":
        print(json.dumps(payload, indent=2))
    else:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        rows = data if isinstance(data, list) else [data]
        table = Table(title="Run Metrics", box=None, padding=(0, 1))
        table.add_column("Task", style="magenta")
        table.add_column("Agent", style="cyan")
        table.add_column("Runs", justify="right")
        table.add_column("Repro %", justify="right")
        table.add_column("Steps P50", justify="right")
        table.add_column("TC P50", justify="right")
        table.add_column("Wall Avg", justify="right")
        for row in rows:
            repro = row.get("reproducibility_rate")
            repro_str = f"{repro * 100:.1f}%" if repro is not None else "—"
            budget = row.get("budget_utilisation") or {}
            steps_p50 = (budget.get("steps") or {}).get("p50") or row.get("steps_p50")
            tc_p50 = (budget.get("tool_calls") or {}).get("p50") or row.get("tool_calls_p50")
            table.add_row(
                str(row.get("task_ref") or "—"),
                str(row.get("agent") or "—"),
                str(row.get("run_count", 0)),
                repro_str,
                str(steps_p50 or "—"),
                str(tc_p50 or "—"),
                str(row.get("avg_wall_clock_s") or "—"),
            )
        console.print(table)
    return 0


def _cmd_runs_mttr(args: argparse.Namespace) -> int:
    from agent_bench.runner.metrics import compute_mttr

    task_ref: str | None = getattr(args, "task", None)
    agent: str | None = getattr(args, "agent", None)
    limit: int = getattr(args, "limit", 500)

    result = compute_mttr(task_ref=task_ref, agent=agent, limit=limit)
    print(json.dumps(result, indent=2))
    return 0


def _cmd_runs_migrate(args: argparse.Namespace) -> int:
    from agent_bench.runner.migration import migrate_run_directory
    from agent_bench.runner.runlog import RUN_LOG_ROOT

    write: bool = getattr(args, "write", False)
    root_arg: str | None = getattr(args, "root", None)
    root = Path(root_arg).resolve() if root_arg else RUN_LOG_ROOT

    report = migrate_run_directory(root=root, write=write)
    payload = {
        "ok": bool(report.get("ok")),
        "root": str(report.get("root")),
        "changed": int(report.get("changed", 0)),
        "files": report.get("files", []),
        "errors": report.get("errors", []),
        "write": write,
    }
    print(json.dumps(payload, indent=2))

    if payload["errors"]:
        return 1
    if not write and payload["changed"] > 0:
        return 1
    return 0


def _cmd_version(args: argparse.Namespace) -> int:
    from agent_bench.runner.runner import SPEC_VERSION
    try:
        version = _meta.version("tracecore")
    except _meta.PackageNotFoundError:
        try:
            version = _meta.version("agent-bench")
        except _meta.PackageNotFoundError:
            version = "0.0.0-dev"
    print(f"runtime: {version}  spec: {SPEC_VERSION} (TraceCore {version})")
    _maybe_print_star_nudge()
    return 0


def _cmd_maintain(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    payload = maintain(
        cwd=cwd,
        pytest_args=args.pytest_args or getattr(args, "_passthrough", None),
        validate_tasks=not args.no_tasks_validate,
        fix_agent_files=args.fix_agent or [],
        dry_run=not args.apply,
    )
    print(dumps_summary(payload))
    return 0 if payload.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-bench", add_help=True)
    parser.add_argument("--config", help="Path to agent-bench.toml (defaults to ./agent-bench.toml)")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run an agent against a task")
    run_sub = run_parser.add_subparsers(dest="run_command")

    pairing_parser = run_sub.add_parser("pairing", help="Run a known-good agent+task pairing by name")
    pairing_parser.add_argument(
        "pairing_name",
        nargs="?",
        help="Pairing name (e.g., log_stream_monitor); omit to auto-detect from CWD",
    )
    pairing_parser.add_argument("--seed", type=int, help="Deterministic seed (defaults to 0)")
    pairing_parser.add_argument("--list", action="store_true", help="List all available pairings and exit")
    pairing_parser.add_argument("--all", action="store_true", help="Run every pairing in sequence and print a summary table")
    pairing_parser.add_argument("--timeout", type=int, metavar="SECONDS", help="Wall-clock timeout per run in seconds")
    pairing_parser.set_defaults(func=_cmd_run_pairing)

    batch_parser = run_sub.add_parser(
        "batch",
        help="Run multiple episodes in parallel",
        description=(
            "Run multiple deterministic episodes in parallel worker processes. "
            "Use this as the current local stepping stone toward distributed-style execution work in Phase 6."
        ),
    )
    batch_parser.add_argument(
        "--batch-file",
        dest="batch_file",
        metavar="JSON",
        help="JSON file with array of {agent, task_ref, seed} job objects; defaults to all pairings",
    )
    batch_parser.add_argument(
        "--workers",
        type=int,
        metavar="N",
        help="Maximum parallel workers (default: auto, up to 8)",
    )
    batch_parser.add_argument("--seed", type=int, default=0, help="Seed for all jobs when using pairings (default: 0)")
    batch_parser.add_argument("--timeout", type=int, metavar="SECONDS", help="Per-job wall-clock timeout")
    batch_parser.add_argument(
        "--strict-spec",
        dest="strict_spec",
        action="store_true",
        help="Run spec compliance check on every result; fail batch if any job is non-compliant",
    )
    batch_parser.set_defaults(func=_cmd_run_batch)

    run_parser.add_argument("--agent", help="Path to the agent module")
    run_parser.add_argument("--task", help="Task reference (e.g., filesystem_hidden_config@1)")
    run_parser.add_argument("--seed", type=int, help="Deterministic seed (defaults to 0)")
    run_parser.add_argument(
        "--replay",
        help="Replay a prior run_id; agent/task/seed default to recorded values and can be overridden",
    )
    run_parser.add_argument(
        "--replay-bundle",
        metavar="BUNDLE_DIR",
        dest="replay_bundle",
        help="Re-run the agent from a baseline bundle and verify the trace matches",
    )
    run_parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: replay enforcement + budget must not exceed baseline (use with --replay-bundle)",
    )
    run_parser.add_argument(
        "--record",
        action="store_true",
        help="Record mode: run the agent, verify determinism by re-running, then seal a baseline bundle. "
             "Not allowed in CI (use --replay-bundle/--strict for gating).",
    )
    run_parser.add_argument(
        "--strict-spec",
        dest="strict_spec",
        action="store_true",
        help="Spec compliance mode: validate the emitted artifact against TraceCore Spec v0.1 "
             "(schema, required metadata, taxonomy). Fails with exit code 1 if non-compliant.",
    )
    run_parser.add_argument("--timeout", type=int, metavar="SECONDS", help="Wall-clock timeout in seconds; exits non-zero if exceeded")
    run_parser.add_argument(
        "--from-config",
        dest="from_config",
        metavar="EPISODE_JSON",
        help="Load agent/task/seed/budget/timeout from an episode config JSON file (overridden by explicit CLI flags)",
    )
    run_parser.set_defaults(func=_cmd_run)

    runs_parser = subparsers.add_parser("runs", help="Inspect stored run artifacts")
    runs_sub = runs_parser.add_subparsers(dest="runs_command")
    runs_list = runs_sub.add_parser("list", help="List recent runs (newest first)")
    runs_list.add_argument("--agent", help="Filter by agent path")
    runs_list.add_argument("--task", dest="task", help="Filter by task reference")
    runs_list.add_argument("--limit", type=int, default=20, help="Maximum runs to return")
    runs_list.add_argument(
        "--failure-type",
        choices=("success",) + FAILURE_TYPES,
        help="Filter by failure type (or 'success' for completed runs)",
    )
    runs_list.set_defaults(func=_cmd_runs_list)

    runs_summary = runs_sub.add_parser("summary", help="Print a compact table of recent runs")
    runs_summary.add_argument("--agent", help="Filter by agent path")
    runs_summary.add_argument("--task", dest="task", help="Filter by task reference")
    runs_summary.add_argument("--limit", type=int, default=20, help="Maximum runs to show (default: 20)")
    runs_summary.add_argument(
        "--failure-type",
        dest="failure_type",
        choices=("success",) + FAILURE_TYPES,
        help="Filter by outcome",
    )
    runs_summary.set_defaults(func=_cmd_runs_summary)

    runs_metrics = runs_sub.add_parser("metrics", help="Compute reproducibility, budget, and taxonomy metrics")
    runs_metrics.add_argument("--agent", help="Filter by agent path")
    runs_metrics.add_argument("--task", dest="task", help="Filter by task reference")
    runs_metrics.add_argument("--limit", type=int, default=500, help="Max runs to consider (default: 500)")
    runs_metrics.add_argument("--format", choices=("json", "table"), default="json", help="Output format (default: json)")
    runs_metrics.set_defaults(func=_cmd_runs_metrics)

    runs_mttr_p = runs_sub.add_parser("mttr", help="Compute mean time to recovery per agent+task+seed")
    runs_mttr_p.add_argument("--agent", help="Filter by agent path")
    runs_mttr_p.add_argument("--task", dest="task", help="Filter by task reference")
    runs_mttr_p.add_argument("--limit", type=int, default=500, help="Max runs to scan (default: 500)")
    runs_mttr_p.set_defaults(func=_cmd_runs_mttr)

    runs_migrate = runs_sub.add_parser(
        "migrate",
        help="Upgrade legacy run artifacts to the current TraceCore schema",
    )
    runs_migrate.add_argument(
        "--root",
        help="Run artifact directory to scan (default: .agent_bench/runs)",
    )
    runs_migrate.add_argument(
        "--write",
        action="store_true",
        help="Rewrite legacy artifacts in place (default: dry-run that exits nonzero if changes are needed)",
    )
    runs_migrate.set_defaults(func=_cmd_runs_migrate)

    baseline_parser = subparsers.add_parser("baseline", help="Compute baseline stats from persisted runs")
    baseline_parser.add_argument("--agent", help="Filter by agent path")
    baseline_parser.add_argument("--task", dest="task", help="Filter by task reference")
    baseline_parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of runs to consider per filter (newest first)",
    )
    baseline_parser.add_argument(
        "--export",
        nargs="?",
        const="",
        help="Persist the baseline to .agent_bench/baselines (optionally supply relative path)",
    )
    baseline_parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("RUN_A", "RUN_B"),
        help="Diff two run artifacts (paths or run_ids) instead of computing aggregate stats",
    )
    baseline_parser.add_argument(
        "--format",
        choices=("json", "text", "pretty"),
        default="pretty",
        help="Output format for --compare (default: pretty)",
    )
    baseline_parser.add_argument(
        "--show-taxonomy",
        action="store_true",
        help="Highlight failure taxonomy changes in --compare output",
    )
    baseline_parser.add_argument(
        "--bundle",
        action="store_true",
        help="Write and verify a baseline bundle for the most recent matching run",
    )
    baseline_parser.add_argument(
        "--verify",
        metavar="BUNDLE_DIR",
        help="Verify an existing baseline bundle directory and print the report",
    )
    baseline_parser.set_defaults(func=_cmd_baseline)

    export_parser = subparsers.add_parser("export", help="Export run artifacts to structured formats")
    export_sub = export_parser.add_subparsers(dest="export_command")
    export_otlp_p = export_sub.add_parser("otlp", help="Export a run artifact as OTLP-compatible JSON spans")
    export_otlp_p.add_argument("run", help="Run artifact path or run_id to export")
    export_otlp_p.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write OTLP JSON to FILE instead of stdout",
    )
    export_otlp_p.set_defaults(func=_cmd_export)

    export_parser.add_argument("--output", help="Write OTLP export to file instead of stdout")

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect the latest (or given) run artifact and summarize llm_trace",
        description=(
            "Inspect a stored run artifact, including telemetry-rich `llm_trace` summaries when present. "
            "Use this when debugging prompt/completion behavior or comparing raw artifacts to dashboard views."
        ),
    )
    inspect_parser.add_argument("--run", help="Path to a run artifact (defaults to latest in .agent_bench/runs)")
    inspect_parser.set_defaults(func=_cmd_inspect)

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify the latest run or a specific run/bundle",
        description=(
            "Verify a recent run artifact and, optionally, compare it against a sealed bundle. "
            "This is the fastest validation step after `tracecore run`, especially when using the session pointer workflow."
        ),
    )
    verify_parser.add_argument(
        "--latest",
        action="store_true",
        help="Verify the latest run (default when no explicit --run/--bundle is provided)",
    )
    verify_parser.add_argument("--run", metavar="RUN", help="Run artifact path or run_id")
    verify_parser.add_argument("--bundle", metavar="DIR", help="Bundle directory to verify against")
    verify_parser.add_argument(
        "--strict",
        action="store_true",
        help="If verifying against a bundle, enforce strict replay rules (budgets must not exceed baseline)",
    )
    verify_parser.add_argument(
        "--strict-spec",
        dest="strict_spec",
        action="store_true",
        help="Validate the run artifact against the TraceCore spec compliance checker",
    )
    verify_parser.add_argument(
        "--prefer-success",
        dest="prefer_success",
        action="store_true",
        help="When using --latest, prefer the latest successful run (default)",
    )
    verify_parser.add_argument(
        "--json",
        dest="json",
        action="store_true",
        help="Emit machine-readable JSON report",
    )
    verify_parser.set_defaults(func=_cmd_verify, prefer_success=True)

    def _cmd_export_no_sub(args: argparse.Namespace) -> int:
        export_parser.print_help()
        return 0

    export_parser.set_defaults(func=_cmd_export_no_sub)

    diff_parser = subparsers.add_parser("diff", help="Diff two run artifacts and surface taxonomy + budget deltas")
    diff_parser.add_argument("run_a", help="First run artifact path or run_id (baseline)")
    diff_parser.add_argument("run_b", help="Second run artifact path or run_id (current)")
    diff_parser.add_argument(
        "--format",
        choices=("pretty", "text", "json", "otlp"),
        default="pretty",
        help="Output format (default: pretty). 'otlp' emits OTLP-compatible JSON spans for each run.",
    )
    diff_parser.set_defaults(func=_cmd_diff)

    bundle_parser = subparsers.add_parser(
        "bundle",
        help="Baseline bundle utilities",
        description=(
            "Seal, inspect, sign, and verify baseline bundles. "
            "Use bundle commands when you need replayable evidence, integrity checks, or ledger-ready artifacts."
        ),
    )
    bundle_sub = bundle_parser.add_subparsers(dest="bundle_command")

    bundle_sign = bundle_sub.add_parser("sign", help="Sign a baseline bundle with Ed25519 key")
    bundle_sign.add_argument("path", help="Path to the bundle directory")
    bundle_sign.add_argument(
        "--key",
        metavar="KEY_FILE",
        help="Path to Ed25519 private key PEM (defaults to agent_bench/ledger/signing_key.pem)",
    )
    bundle_sign.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format (default: text)",
    )
    bundle_sign.set_defaults(func=_cmd_bundle_sign)

    bundle_verify = bundle_sub.add_parser("verify", help="Verify integrity of a baseline bundle directory")
    bundle_verify.add_argument("path", help="Path to the bundle directory")
    bundle_verify.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format (default: text)",
    )
    bundle_verify.set_defaults(func=_cmd_bundle_verify)

    bundle_seal = bundle_sub.add_parser("seal", help="Seal a baseline bundle from the latest (or given) run")
    bundle_seal.add_argument("--latest", action="store_true", help="Seal from the latest successful run (default)")
    bundle_seal.add_argument("--run", metavar="RUN", help="Run artifact path or run_id to seal from")
    bundle_seal.add_argument("--sign", action="store_true", help="Sign the sealed bundle")
    bundle_seal.add_argument("--key", metavar="KEY_FILE", help="Signing key path (Ed25519 PEM)")
    bundle_seal.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format (default: text)",
    )
    bundle_seal.set_defaults(func=_cmd_bundle_seal)

    bundle_status = bundle_sub.add_parser("status", help="List recent bundles and their integrity status")
    bundle_status.add_argument("--limit", type=int, default=10, help="Max bundles to show (default: 10)")
    bundle_status.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format (default: text)",
    )
    bundle_status.set_defaults(func=_cmd_bundle_status)

    def _cmd_bundle_no_sub(args: argparse.Namespace) -> int:
        bundle_parser.print_help()
        return 0

    bundle_parser.set_defaults(func=_cmd_bundle_no_sub)

    ledger_parser = subparsers.add_parser(
        "ledger",
        help="Inspect TraceCore Ledger entries",
        description=(
            "Inspect and verify TraceCore Ledger entries for signed bundles and registry state. "
            "Use this when auditing evidence, validating signatures, or troubleshooting trust-pipeline flows."
        ),
    )
    ledger_sub = ledger_parser.add_subparsers(dest="ledger_command")
    ledger_parser.add_argument(
        "--show",
        metavar="AGENT",
        help="Show detailed entry for AGENT (path or stem)",
    )
    ledger_parser.set_defaults(func=_cmd_ledger)

    ledger_verify_parser = ledger_sub.add_parser("verify", help="Verify Ed25519 signatures of bundles or the registry")
    ledger_verify_parser.add_argument(
        "--bundle",
        metavar="BUNDLE_DIR",
        help="Verify signature of a local bundle directory",
    )
    ledger_verify_parser.add_argument(
        "--entry",
        metavar="AGENT",
        help="Verify all signed task rows for a ledger entry (path or stem)",
    )
    ledger_verify_parser.add_argument(
        "--registry",
        action="store_true",
        help="Verify the top-level registry signature embedded in registry.json",
    )
    ledger_verify_parser.set_defaults(func=_cmd_ledger_verify)

    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the web UI dashboard (FastAPI/uvicorn)")
    dashboard_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    dashboard_parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    dashboard_parser.add_argument("--reload", action="store_true", help="Enable autoreload (dev only)")
    dashboard_parser.set_defaults(func=_cmd_dashboard)

    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Launch a colorful wizard to pick agent/task/seed before running",
    )
    interactive_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors for the interactive wizard",
    )
    interactive_parser.add_argument(
        "--save-session",
        action="store_true",
        help="Save agent/task/seed selections to .agent_bench/.wizard_session.json for future runs",
    )
    interactive_parser.add_argument(
        "--plugins",
        action="store_true",
        help="Include plugin tasks in discovery (default: bundled tasks only)",
    )
    interactive_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the command without executing it",
    )
    interactive_parser.set_defaults(func=_cmd_interactive)

    tasks_parser = subparsers.add_parser("tasks", help="Inspect and validate task metadata")
    tasks_sub = tasks_parser.add_subparsers(dest="tasks_command")
    tasks_validate = tasks_sub.add_parser("validate", help="Validate task manifests and registry entries")
    tasks_validate.add_argument(
        "--path",
        action="append",
        help="Path to a task directory (repeatable)",
    )
    tasks_validate.add_argument(
        "--registry",
        action="store_true",
        help="Validate all registry entries (including plugins)",
    )
    tasks_validate.set_defaults(func=_cmd_tasks_validate)

    tasks_lint = tasks_sub.add_parser(
        "lint",
        help="Lint all registry entries for plugin contract compliance (action_schema, budgets, sandbox)",
    )
    tasks_lint.add_argument(
        "--path",
        action="append",
        help="Lint a specific task directory (repeatable; defaults to full registry)",
    )
    tasks_lint.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format (default: text)",
    )
    tasks_lint.set_defaults(func=_cmd_tasks_lint)

    maintain_parser = subparsers.add_parser(
        "maintain",
        help="Run task validation + pytest and optionally apply guarded fixes",
    )
    maintain_parser.add_argument(
        "--cwd",
        help="Working directory to run checks from (default: current directory)",
    )
    maintain_parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        help="Additional args passed to pytest (prefix with --)",
    )
    maintain_parser.add_argument(
        "--no-tasks-validate",
        action="store_true",
        help="Skip agent-bench tasks validate --registry",
    )
    maintain_parser.add_argument(
        "--fix-agent",
        action="append",
        help="Agent file path to apply guarded fixers to (repeatable)",
    )
    maintain_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply fixes in-place (default: dry-run)",
    )
    maintain_parser.set_defaults(func=_cmd_maintain)

    new_agent_parser = subparsers.add_parser(
        "new-agent",
        help="Scaffold a new agent stub with the correct reset/observe/act interface",
    )
    new_agent_parser.add_argument(
        "name",
        help="Agent name in snake_case or kebab-case (e.g., my_agent or my-agent)",
    )
    new_agent_parser.add_argument(
        "--output-dir",
        default="agents",
        metavar="DIR",
        help="Directory to write the stub into (default: agents/)",
    )
    new_agent_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing file",
    )
    new_agent_parser.set_defaults(func=_cmd_new_agent)

    openclaw_parser = subparsers.add_parser(
        "openclaw",
        help="Scaffold and test a TraceCore adapter for an OpenClaw agent",
    )
    openclaw_parser.add_argument(
        "--agent-id",
        dest="agent_id",
        metavar="ID",
        help="OpenClaw agent ID from openclaw.json (auto-detected if only one agent exists)",
    )
    openclaw_parser.add_argument(
        "--task",
        default="filesystem_hidden_config@1",
        help="Task ref to test against (default: filesystem_hidden_config@1)",
    )
    openclaw_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed for the test run (default: 0)",
    )
    openclaw_parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        metavar="SECONDS",
        help="Wall-clock timeout for the test run",
    )
    openclaw_parser.add_argument(
        "--gateway",
        action="store_true",
        help="Also scaffold a gateway-wired adapter (requires running OpenClaw gateway)",
    )
    openclaw_parser.set_defaults(func=_cmd_openclaw)

    openclaw_export_parser = subparsers.add_parser(
        "openclaw-export",
        help="Export a certified TraceCore bundle for a tested OpenClaw adapter",
    )
    openclaw_export_parser.add_argument(
        "--agent-id",
        dest="agent_id",
        metavar="ID",
        help="OpenClaw agent ID (auto-detected if only one agent exists)",
    )
    openclaw_export_parser.add_argument(
        "--out-dir",
        dest="out_dir",
        default="tracecore_export",
        metavar="DIR",
        help="Output directory for the bundle (default: tracecore_export/)",
    )
    openclaw_export_parser.set_defaults(func=_cmd_openclaw_export)

    version_parser = subparsers.add_parser("version", help="Print runtime and spec version")
    version_parser.set_defaults(func=_cmd_version)

    args, unknown = parser.parse_known_args()
    if unknown and getattr(args, "command", None) == "maintain":
        setattr(args, "_passthrough", unknown)

    config = _load_config_from_args(getattr(args, "config", None))
    setattr(args, "_config", config)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
