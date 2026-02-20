"""
Simple proof of concept demonstrating TraceCore agent execution.

This demo shows how to:
1. Load a task from the registry
2. Initialize an agent
3. Run the agent against the task
4. Display results

Example usage:
    python demo.py --task dice_game --agent dice_game_agent
    python demo.py --task rate_limited_chain --agent chain_agent --verbose
"""

import sys
import json
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directories to path for imports
benchmark_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(benchmark_root))
sys.path.insert(0, str(benchmark_root / "agents"))
sys.path.insert(0, str(benchmark_root / "tasks"))

from agent_bench.runner.runner import run
from agent_bench.tasks.loader import load_task


def print_separator(char="=", length=60):
    """Print a visual separator."""
    print(char * length)


def run_demo(task_name: str, agent_name: str, verbose: bool = False, seed: int = 0):
    """Run a simple agent demo."""
    
    print_separator()
    print(f"🎯 TraceCore Agent Demo")
    print_separator()
    print(f"Task: {task_name}")
    print(f"Agent: {agent_name}")
    print(f"Seed: {seed}")
    print_separator()
    
    # Construct agent path - must be absolute for the loader
    agent_file = benchmark_root / "agents" / f"{agent_name}.py"
    
    if not agent_file.exists():
        print(f"❌ Error: Agent file not found at {agent_file}")
        return
    
    agent_path = str(agent_file)
    
    # Load task metadata for display
    print("\n🔧 Loading task metadata...")
    try:
        task = load_task(task_name)
        print(f"✓ Task loaded: {task.get('name', task_name)}")
        print(f"  Description: {task.get('description', 'N/A')}")
        budgets = task.get('default_budget', {})
        print(f"  Max steps: {budgets.get('steps', 'unlimited')}")
        print(f"  Max tool calls: {budgets.get('tool_calls', 'unlimited')}")
    except Exception as e:
        print(f"⚠️  Could not load task metadata: {e}")
    
    # Run episode
    print(f"\n🚀 Starting episode (agent={agent_path}, task={task_name}, seed={seed})...")
    print_separator("-")
    
    try:
        result = run(agent_path, task_name, seed=seed)
        
        print_separator("-")
        print("\n📈 Episode Results:")
        print(f"  Success: {result.get('success', False)}")
        print(f"  Termination: {result.get('termination_reason', 'unknown')}")
        print(f"  Steps used: {result.get('steps_used', 0)}")
        print(f"  Tool calls used: {result.get('tool_calls_used', 0)}")
        
        if result.get('failure_reason'):
            print(f"  Failure reason: {result['failure_reason']}")
        if result.get('failure_type'):
            print(f"  Failure type: {result['failure_type']}")
        
        metrics = result.get('metrics', {})
        if metrics:
            print(f"\n� Metrics:")
            for key, value in metrics.items():
                print(f"    {key}: {value}")
        
        if verbose and result.get('action_trace'):
            print(f"\n📜 Action Trace ({len(result['action_trace'])} actions):")
            for i, action in enumerate(result['action_trace'][:10], 1):  # Show first 10
                action_type = action.get('action', {}).get('type', 'unknown')
                print(f"    {i}. {action_type}")
            if len(result['action_trace']) > 10:
                print(f"    ... and {len(result['action_trace']) - 10} more")
        
        print_separator()
        
        if result.get('success'):
            print("🎉 Episode completed successfully!")
        else:
            print(f"❌ Episode failed: {result.get('failure_reason', 'unknown')}")
            
    except Exception as e:
        print(f"\n❌ Error during episode execution:")
        print(f"   {type(e).__name__}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return
    
    print_separator()


def main():
    """Main entry point with argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Simple TraceCore agent demonstration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo.py --task dice_game --agent dice_game_agent
  python demo.py --task rate_limited_chain --agent chain_agent --verbose
  python demo.py --list-tasks
  python demo.py --list-agents
        """
    )
    
    parser.add_argument(
        "--task",
        type=str,
        help="Task name to run (e.g., dice_game, rate_limited_chain)"
    )
    parser.add_argument(
        "--agent",
        type=str,
        help="Agent name to use (e.g., dice_game_agent, chain_agent)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for deterministic execution (default: 0)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="List available tasks"
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List available agents"
    )
    
    args = parser.parse_args()
    
    # List tasks
    if args.list_tasks:
        print("📋 Available Tasks:")
        tasks_dir = benchmark_root / "tasks"
        for task_dir in sorted(tasks_dir.iterdir()):
            if task_dir.is_dir() and not task_dir.name.startswith("_"):
                readme = task_dir / "README.md"
                if readme.exists():
                    first_line = readme.read_text().split("\n")[0].strip("# ")
                    print(f"  • {task_dir.name}: {first_line}")
                else:
                    print(f"  • {task_dir.name}")
        return
    
    # List agents
    if args.list_agents:
        print("🤖 Available Agents:")
        agents_dir = benchmark_root / "agents"
        for agent_file in sorted(agents_dir.glob("*.py")):
            if agent_file.name != "__init__.py":
                agent_name = agent_file.stem
                # Try to read docstring
                content = agent_file.read_text()
                lines = content.split("\n")
                desc = "No description"
                for line in lines[:10]:
                    if line.strip() and not line.strip().startswith("#") and '"""' not in line:
                        desc = line.strip()
                        break
                print(f"  • {agent_name}")
        return
    
    # Validate required arguments
    if not args.task or not args.agent:
        parser.print_help()
        print("\n❌ Error: Both --task and --agent are required")
        sys.exit(1)
    
    # Run the demo
    run_demo(args.task, args.agent, args.verbose, args.seed)


if __name__ == "__main__":
    main()
