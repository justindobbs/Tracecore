"""Interactive CLI wizard for TraceCore."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from agent_bench.config import AgentBenchConfig
from agent_bench.tasks.registry import list_task_descriptors

AGENTS_ROOT = Path("agents")
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
}


@dataclass(frozen=True)
class TaskOption:
    ref: str
    suite: str
    description: str


def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _discover_agents() -> list[str]:
    if not AGENTS_ROOT.exists():
        return []
    return [str(path).replace("\\", "/") for path in sorted(AGENTS_ROOT.glob("*.py"))]


def _discover_tasks() -> list[TaskOption]:
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
        options.append(TaskOption(ref=ref, suite=desc.suite, description=desc.description))
    return options


def _print_table(console: Console, table: Table) -> None:
    console.print()
    console.print(table)
    console.print()


def _agent_table(agents: Sequence[str], default_agent: str | None) -> Table:
    table = Table(title="Discovered Agents", show_lines=True)
    table.add_column("#", style="cyan", justify="center")
    table.add_column("Path", style="bright_white")
    table.add_column("Summary", style="green")
    for idx, agent in enumerate(agents, start=1):
        label = agent
        if default_agent and agent == default_agent:
            label = f"{agent} (default)"
        summary = AGENT_SUMMARIES.get(agent, "Local agent script")
        table.add_row(str(idx), label, summary)
    return table


def _task_table(tasks: Sequence[TaskOption], default_task: str | None) -> Table:
    table = Table(title="Bundled Tasks", show_lines=True)
    table.add_column("#", style="cyan", justify="center")
    table.add_column("Task", style="bright_white")
    table.add_column("Suite", style="magenta")
    table.add_column("Description", style="green")
    for idx, task in enumerate(tasks, start=1):
        ref = task.ref
        if default_task and ref == default_task:
            ref = f"{ref} (default)"
        table.add_row(str(idx), ref, task.suite or "—", task.description or "")
    return table


def _manual_entry(console: Console, prompt: str, default: str | None = None) -> str:
    while True:
        value = Prompt.ask(prompt, default=default or None).strip()
        if value:
            return value
        if default:
            return default
        console.print("[bold red]Please enter a value or Ctrl+C to abort.[/bold red]")


def _prompt_agent(console: Console, agents: Sequence[str], default_agent: str | None) -> str:
    if agents:
        _print_table(console, _agent_table(agents, default_agent))
    else:
        console.print("[yellow]No agent scripts found under ./agents — entering manual path.[/yellow]")
        return _manual_entry(console, "Agent path")

    default_idx = agents.index(default_agent) + 1 if default_agent in agents else None
    instructions = "Enter the agent number, press Enter for default, or type 'm' for a manual path"
    while True:
        raw = Prompt.ask(
            f"Agent selection ({instructions})",
            default=str(default_idx) if default_idx else None,
        ).strip()
        if not raw:
            if default_agent:
                return default_agent
            console.print("[yellow]No default configured — select a number or type 'm'.[/yellow]")
            continue
        lowered = raw.lower()
        if lowered in {"m", "manual", "path"}:
            return _manual_entry(console, "Agent path", default_agent)
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(agents):
                return agents[idx - 1]
        console.print("[bold red]Invalid selection. Try again.[/bold red]")


def _prompt_task(console: Console, tasks: Sequence[TaskOption], default_task: str | None) -> str:
    if tasks:
        _print_table(console, _task_table(tasks, default_task))
    else:
        console.print("[yellow]Task registry not available — entering task reference manually.[/yellow]")
        return _manual_entry(console, "Task reference (e.g., filesystem_hidden_config@1)", default_task)

    default_idx = None
    if default_task:
        for idx, task in enumerate(tasks, start=1):
            if task.ref == default_task:
                default_idx = idx
                break
    instructions = "Enter the task number, press Enter for default, or type 'm' for manual entry"
    while True:
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
        if lowered in {"m", "manual", "task"}:
            return _manual_entry(console, "Task reference", default_task)
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(tasks):
                return tasks[idx - 1].ref
        console.print("[bold red]Invalid selection. Try again.[/bold red]")


def _prompt_seed(console: Console, default_seed: int | None) -> int:
    seed_default = default_seed if default_seed is not None else 0
    while True:
        raw = Prompt.ask("Seed", default=str(seed_default)).strip()
        try:
            return int(raw)
        except ValueError:
            console.print("[bold red]Seed must be an integer.[/bold red]")


def _summary_panel(agent: str, task: str, seed: int) -> Panel:
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="bright_white")
    table.add_row("Agent", agent)
    table.add_row("Task", task)
    table.add_row("Seed", str(seed))
    return Panel(table, title="Deterministic Episode", border_style="green")


def run_wizard(
    *,
    config: AgentBenchConfig | None = None,
    console: Console | None = None,
    no_color: bool = False,
) -> tuple[str, str, int] | None:
    """Launch the interactive wizard. Returns (agent, task, seed) or None if aborted."""

    if console is None:
        console = Console(no_color=no_color)

    if not _is_tty():
        console.print("[bold red]Interactive mode requires a TTY-enabled terminal.[/bold red]")
        return None

    console.print(Panel(WELCOME_MESSAGE, title="TraceCore", border_style="blue", subtitle="Deterministic Episode Runtime"))

    default_agent = config.get_default_agent() if config else None
    default_task = config.get_default_task() if config else None
    default_seed = config.get_seed() if config else None

    agents = _discover_agents()
    tasks = _discover_tasks()

    try:
        agent = _prompt_agent(console, agents, default_agent)
        task = _prompt_task(console, tasks, default_task)
        seed = _prompt_seed(console, default_seed)
    except KeyboardInterrupt:
        console.print("\n[bold red]Interactive session cancelled.[/bold red]")
        return None

    console.print(_summary_panel(agent, task, seed))
    if not Confirm.ask("Start this run now?", default=True):
        console.print("[yellow]Aborted before launching the run.[/yellow]")
        return None

    console.print("[green]Launching agent-bench run...[/green]\n")
    return agent, task, seed
