"""Interactive CLI wizard for TraceCore."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from agent_bench.config import AgentBenchConfig
from agent_bench.runner.baseline import summarize_runs
from agent_bench.runner.runlog import iter_runs
from agent_bench.tasks.registry import list_task_descriptors

AGENTS_ROOT = Path("agents")
SESSION_PATH = Path(".agent_bench") / ".wizard_session.json"
WELCOME_MESSAGE = (
    "Welcome to TraceCore! Let's wire up a deterministic episode run with a friendly wizard."
)
AGENT_SUMMARIES = {
    "agents/toy_agent.py": "Filesystem baseline (ToyAgent)",
    "agents/naive_llm_agent.py": "Minimal filesystem loop (NaiveLLMLoop)",
    "agents/rate_limit_agent.py": "API quota baseline (RateLimitAgent)",
    "agents/chain_agent.py": "Handshake + rate-limit orchestration (ChainAgent)",
    "agents/cheater_agent.py": "Defense tester (CheaterSim)",
    "agents/ops_triage_agent.py": "Operations suite reference (OpsTriage)",
    "agents/log_stream_monitor_agent.py": "Log stream patrol + trigger detection (LogStreamMonitor)",
}


@dataclass(frozen=True)
class TaskOption:
    ref: str
    suite: str
    description: str
    budgets: dict[str, int] | None = None


@dataclass(frozen=True)
class Pairing:
    agent: str
    task_ref: str
    success_rate: float
    runs: int
    last_success: bool


def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _discover_agents() -> list[str]:
    if not AGENTS_ROOT.exists():
        return []
    return [str(path).replace("\\", "/") for path in sorted(AGENTS_ROOT.glob("*.py"))]


def _discover_tasks(*, include_plugins: bool = False) -> list[TaskOption]:
    try:
        descriptors = list_task_descriptors()
    except Exception:
        return []
    options: list[TaskOption] = []
    seen: set[str] = set()
    for desc in descriptors:
        ref = f"{desc.id}@{desc.version}"
        if ref in seen:
            continue
        seen.add(ref)
        budgets = desc.metadata.get("default_budget") if desc.metadata else None
        options.append(TaskOption(ref=ref, suite=desc.suite, description=desc.description, budgets=budgets))
    return options


def _print_table(console: Console, table: Table) -> None:
    console.print()
    console.print(table)
    console.print()


def _agent_table(agents: Sequence[str], default_agent: str | None) -> Table:
    table = Table(title="Step 1/3: Select Agent", box=None, padding=(0, 1))
    table.add_column("#", style="cyan", justify="center", no_wrap=True)
    table.add_column("Path", style="bright_white", no_wrap=True)
    table.add_column("Summary", style="green")
    for idx, agent in enumerate(agents, start=1):
        label = agent
        if default_agent and agent == default_agent:
            label = f"{agent} (default)"
        summary = AGENT_SUMMARIES.get(agent, "Local agent script")
        table.add_row(str(idx), label, summary)
    return table


def _discover_pairings(limit: int = 5) -> list[Pairing]:
    """Find successful agent-task pairings from baseline data."""
    try:
        all_runs = list(iter_runs())
        if not all_runs:
            return []
        summaries = summarize_runs(all_runs)
        # Filter to pairings with at least one success
        successful = [s for s in summaries if s.get("success_rate", 0) > 0]
        # Sort by success rate (desc), then run count (desc)
        successful.sort(key=lambda s: (s.get("success_rate", 0), s.get("runs", 0)), reverse=True)
        # Convert to Pairing objects
        pairings = []
        for summary in successful[:limit]:
            pairings.append(
                Pairing(
                    agent=summary["agent"],
                    task_ref=summary["task_ref"],
                    success_rate=summary["success_rate"],
                    runs=summary["runs"],
                    last_success=summary.get("last_success", False),
                )
            )
        return pairings
    except Exception:
        return []


def _pairings_table(pairings: Sequence[Pairing]) -> Table:
    table = Table(title="Suggested Pairings (from baseline data)", box=None, padding=(0, 1))
    table.add_column("#", style="cyan", justify="center", no_wrap=True)
    table.add_column("Agent", style="bright_white", no_wrap=True)
    table.add_column("Task", style="bright_white", no_wrap=True)
    table.add_column("Success", style="green", justify="center", no_wrap=True)
    table.add_column("Last", style="yellow", justify="center", no_wrap=True)
    for idx, pairing in enumerate(pairings, start=1):
        successes = int(pairing.success_rate * pairing.runs)
        success_str = f"{successes}/{pairing.runs}"
        last_str = "✓" if pairing.last_success else "✗"
        table.add_row(f"p{idx}", pairing.agent, pairing.task_ref, success_str, last_str)
    return table


def _task_table(tasks: Sequence[TaskOption], default_task: str | None) -> Table:
    table = Table(title="Step 2/3: Select Task", box=None, padding=(0, 1))
    table.add_column("#", style="cyan", justify="center", no_wrap=True)
    table.add_column("Task", style="bright_white", no_wrap=True)
    table.add_column("Suite", style="magenta", no_wrap=True)
    table.add_column("Budgets", style="yellow", no_wrap=True)
    table.add_column("Description", style="green")
    for idx, task in enumerate(tasks, start=1):
        ref = task.ref
        if default_task and ref == default_task:
            ref = f"{ref} (default)"
        budget_str = "—"
        if task.budgets:
            steps = task.budgets.get("steps", "?")
            calls = task.budgets.get("tool_calls", "?")
            budget_str = f"s:{steps} c:{calls}"
        table.add_row(str(idx), ref, task.suite or "—", budget_str, task.description or "")
    return table


def _validate_agent_path(path: str) -> tuple[bool, str | None]:
    """Validate that an agent file exists and implements the required interface."""
    agent_path = Path(path)
    if not agent_path.exists():
        return False, f"Agent file not found: {path}"
    if not agent_path.is_file():
        return False, f"Agent path is not a file: {path}"
    try:
        content = agent_path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"Could not read agent file: {exc}"
    if not re.search(r"class\s+\w*Agent\w*", content):
        return False, "Agent file must define a class with 'Agent' in the name"
    required_methods = ["reset", "observe", "act"]
    for method in required_methods:
        if not re.search(rf"def\s+{method}\s*\(", content):
            return False, f"Agent class must implement '{method}' method"
    return True, None


def _fuzzy_filter(items: Sequence[str], query: str) -> list[str]:
    """Filter items by case-insensitive substring matching."""
    query_lower = query.lower()
    return [item for item in items if query_lower in item.lower()]


def _fuzzy_filter_tasks(tasks: Sequence[TaskOption], query: str) -> list[TaskOption]:
    """Filter tasks by case-insensitive substring matching on ref or description."""
    query_lower = query.lower()
    return [
        task for task in tasks
        if query_lower in task.ref.lower() or (task.description and query_lower in task.description.lower())
    ]


def _show_help(console: Console, context: str) -> None:
    """Display context-sensitive help."""
    help_text = {
        "agent": "Select an agent by number, type 'm' for manual path, filter by typing text, or '?' for help.",
        "task": "Select a task by number, type 'm' for manual entry, filter by typing text, or '?' for help.",
        "seed": "Common seeds: 0 (baseline), 42 (demo), or any integer for custom runs.",
    }
    message = help_text.get(context, "No help available for this context.")
    console.print(Panel(message, title="Help", border_style="blue"))


def _manual_entry(console: Console, prompt: str, default: str | None = None) -> str:
    while True:
        value = Prompt.ask(prompt, default=default or None).strip()
        if value:
            return value
        if default:
            return default
        console.print("[bold red]Please enter a value or Ctrl+C to abort.[/bold red]")


def _prompt_agent(console: Console, agents: Sequence[str], default_agent: str | None) -> str:
    filtered_agents = list(agents)
    show_table = True
    
    while True:
        if show_table:
            if filtered_agents:
                _print_table(console, _agent_table(filtered_agents, default_agent))
            else:
                console.print("[yellow]No agent scripts found under ./agents — entering manual path.[/yellow]")
                path = _manual_entry(console, "Agent path")
                is_valid, error = _validate_agent_path(path)
                if is_valid:
                    return path
                console.print(f"[bold red]Validation failed: {error}[/bold red]")
                console.print("[yellow]Please try again or Ctrl+C to abort.[/yellow]")
                continue
        show_table = True

        default_idx = filtered_agents.index(default_agent) + 1 if default_agent and default_agent in filtered_agents else None
        instructions = "number, 'm' (manual), text to filter, or '?' (help)"
        raw = Prompt.ask(
            f"Agent selection ({instructions})",
            default=str(default_idx) if default_idx else None,
        ).strip()
        
        if not raw:
            if default_agent:
                is_valid, error = _validate_agent_path(default_agent)
                if is_valid:
                    return default_agent
                console.print(f"[bold red]Default agent validation failed: {error}[/bold red]")
                continue
            console.print("[yellow]No default configured — select a number or type 'm'.[/yellow]")
            continue
        
        lowered = raw.lower()
        if lowered in {"?", "h", "help"}:
            _show_help(console, "agent")
            show_table = False
            continue
        if lowered in {"m", "manual", "path"}:
            path = _manual_entry(console, "Agent path", default_agent)
            is_valid, error = _validate_agent_path(path)
            if is_valid:
                return path
            console.print(f"[bold red]Validation failed: {error}[/bold red]")
            continue
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(filtered_agents):
                selected = filtered_agents[idx - 1]
                is_valid, error = _validate_agent_path(selected)
                if is_valid:
                    return selected
                console.print(f"[bold red]Validation failed: {error}[/bold red]")
                continue
            console.print("[bold red]Invalid selection. Try again.[/bold red]")
            continue
        
        # Treat as filter query
        new_filtered = _fuzzy_filter(agents, raw)
        if not new_filtered:
            console.print(f"[yellow]No agents match '{raw}'. Showing all agents.[/yellow]")
            filtered_agents = list(agents)
        else:
            filtered_agents = new_filtered


def _prompt_task(console: Console, tasks: Sequence[TaskOption], default_task: str | None) -> str:
    filtered_tasks = list(tasks)
    show_table = True
    
    while True:
        if show_table:
            if filtered_tasks:
                _print_table(console, _task_table(filtered_tasks, default_task))
            else:
                console.print("[yellow]Task registry not available — entering task reference manually.[/yellow]")
                return _manual_entry(console, "Task reference (e.g., filesystem_hidden_config@1)", default_task)
        show_table = True

        default_idx = None
        if default_task:
            for idx, task in enumerate(filtered_tasks, start=1):
                if task.ref == default_task:
                    default_idx = idx
                    break
        
        instructions = "number, 'm' (manual), text to filter, or '?' (help)"
        raw = Prompt.ask(
            f"Task selection ({instructions})",
            default=str(default_idx) if default_idx else None,
        ).strip()
        
        if not raw:
            if default_task:
                return default_task
            console.print("[yellow]No default configured — select a number or type 'm'.[/yellow]")
            continue
        
        lowered = raw.lower()
        if lowered in {"?", "h", "help"}:
            _show_help(console, "task")
            show_table = False
            continue
        if lowered in {"m", "manual", "task"}:
            return _manual_entry(console, "Task reference", default_task)
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(filtered_tasks):
                return filtered_tasks[idx - 1].ref
            console.print("[bold red]Invalid selection. Try again.[/bold red]")
            continue
        
        # Treat as filter query
        new_filtered = _fuzzy_filter_tasks(tasks, raw)
        if not new_filtered:
            console.print(f"[yellow]No tasks match '{raw}'. Showing all tasks.[/yellow]")
            filtered_tasks = list(tasks)
        else:
            filtered_tasks = new_filtered


def _prompt_seed(console: Console, default_seed: int | None) -> int:
    seed_default = default_seed if default_seed is not None else 0
    console.print("\n[bold cyan]Step 3/3: Seed[/bold cyan]")
    while True:
        raw = Prompt.ask("Seed (or '?' for help)", default=str(seed_default)).strip()
        if raw.lower() in {"?", "h", "help"}:
            _show_help(console, "seed")
            continue
        try:
            return int(raw)
        except ValueError:
            console.print("[bold red]Seed must be an integer.[/bold red]")


def _load_session() -> dict | None:
    """Load saved session from disk."""
    if not SESSION_PATH.exists():
        return None
    try:
        data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        return data
    except Exception:
        return None


def _save_session(agent: str, task: str, seed: int) -> None:
    """Save session to disk."""
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "agent": agent,
        "task": task,
        "seed": seed,
    }
    SESSION_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _summary_panel(agent: str, task: str, seed: int) -> Panel:
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="bright_white")
    table.add_row("Agent", agent)
    table.add_row("Task", task)
    table.add_row("Seed", str(seed))
    return Panel(table, title="Deterministic Episode", border_style="green", subtitle="Step 3/3: Confirm & Launch")


def run_wizard(
    *,
    config: AgentBenchConfig | None = None,
    console: Console | None = None,
    no_color: bool = False,
    save_session: bool = False,
    include_plugins: bool = False,
    dry_run: bool = False,
) -> tuple[str, str, int] | None:
    """Launch the interactive wizard. Returns (agent, task, seed) or None if aborted."""

    if console is None:
        console = Console(no_color=no_color)

    if not _is_tty():
        console.print("[bold red]Interactive mode requires a TTY-enabled terminal.[/bold red]")
        return None

    console.print(Panel(WELCOME_MESSAGE, title="TraceCore", border_style="blue", subtitle="Deterministic Episode Runtime"))

    # Load defaults from config, then fall back to session if no config defaults
    default_agent = config.get_default_agent() if config else None
    default_task = config.get_default_task() if config else None
    default_seed = config.get_seed() if config else None
    
    if not default_agent or not default_task or default_seed is None:
        session = _load_session()
        if session:
            default_agent = default_agent or session.get("agent")
            default_task = default_task or session.get("task")
            default_seed = default_seed if default_seed is not None else session.get("seed")

    # Check for suggested pairings
    pairings = _discover_pairings()
    agent: str | None = None
    task: str | None = None
    
    if pairings:
        console.print()
        _print_table(console, _pairings_table(pairings))
        pairing_prompt = "Select a pairing (p1-p{}) or press Enter to choose manually".format(len(pairings))
        pairing_choice = Prompt.ask(pairing_prompt, default="").strip().lower()
        
        if pairing_choice.startswith("p") and len(pairing_choice) > 1 and pairing_choice[1:].isdigit():
            idx = int(pairing_choice[1:])
            if 1 <= idx <= len(pairings):
                selected_pairing = pairings[idx - 1]
                agent = selected_pairing.agent
                task = selected_pairing.task_ref
                console.print(f"[green]✓ Selected pairing: {agent} + {task}[/green]")
                console.print(f"[dim]Skipping agent and task selection...[/dim]")

    agents = _discover_agents()
    tasks = _discover_tasks(include_plugins=include_plugins)

    try:
        if agent is None:
            agent = _prompt_agent(console, agents, default_agent)
        if task is None:
            task = _prompt_task(console, tasks, default_task)
        seed = _prompt_seed(console, default_seed)
    except KeyboardInterrupt:
        console.print("\n[bold red]Interactive session cancelled.[/bold red]")
        return None

    console.print(_summary_panel(agent, task, seed))
    
    if dry_run:
        console.print("\n[bold yellow][Dry-Run Mode][/bold yellow]")
        console.print("The following command would be executed:\n")
        console.print(f"  [cyan]agent-bench run --agent {agent} --task {task} --seed {seed}[/cyan]\n")
        console.print("[dim]No run was performed.[/dim]")
        return None
    
    if not Confirm.ask("Start this run now?", default=True):
        console.print("[yellow]Aborted before launching the run.[/yellow]")
        return None

    if save_session:
        try:
            _save_session(agent, task, seed)
            console.print("[dim]Session saved to .agent_bench/.wizard_session.json[/dim]")
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not save session: {exc}[/yellow]")

    console.print("[green]Launching agent-bench run...[/green]\n")
    return agent, task, seed
