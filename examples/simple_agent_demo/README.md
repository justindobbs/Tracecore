# Simple Agent Demo

A proof of concept application demonstrating how to run TraceCore agents against tasks.

## Overview

This demo shows the core TraceCore workflow:
1. **Load a task** from the task registry
2. **Initialize an agent** from the agents directory
3. **Run an episode** where the agent interacts with the task environment
4. **Display results** including validation outcomes

## Quick Start

### Run the Dice Game Demo

The simplest example - a deterministic dice game where the agent tries to roll a 4:

```bash
cd examples/simple_agent_demo
python demo.py --task dice_game --agent dice_game_agent
```

### Run the Chain Agent Demo

A more complex example showing API rate limiting and handshake flows:

```bash
python demo.py --task rate_limited_chain --agent chain_agent --verbose
```

## Available Commands

### List Available Tasks
```bash
python demo.py --list-tasks
```

### List Available Agents
```bash
python demo.py --list-agents
```

### Run with Verbose Output
```bash
python demo.py --task dice_game --agent dice_game_agent --verbose
```

## Example Output

```
============================================================
🎯 TraceCore Agent Demo
============================================================
Task: dice_game
Agent: dice_game_agent
============================================================

🔧 Loading task...
✓ Task loaded: Dice Game
  Description: Simple dice game for testing record mode
  Max steps: 3

🤖 Loading agent from agents/dice_game_agent.py...
✓ Agent loaded successfully

🚀 Starting episode...
------------------------------------------------------------

📈 Episode Results:
  Status: success
  Steps taken: 2

📤 Agent Output:
    result: Winner! You rolled 4

✅ Validation Result:
    Success: True
    Score: 1.0

============================================================
🎉 Episode completed successfully!
============================================================
```

## How It Works

### 1. Task Loading
Tasks are loaded from the `tasks/` directory using the TraceCore task loader. Each task defines:
- Available actions the agent can take
- Environment setup and state management
- Validation criteria for success

### 2. Agent Initialization
Agents implement the TraceCore agent interface with three key methods:
- `reset(task_spec)` - Initialize for a new episode
- `observe(observation)` - Receive environment feedback
- `act()` - Return the next action to take

### 3. Episode Execution
The runner executes a loop:
1. Agent receives observation
2. Agent returns an action
3. Environment processes the action
4. Environment returns new observation
5. Repeat until success, failure, or max steps

### 4. Validation
After the episode completes, the task's validator checks if the agent achieved the goal.

## Extending the Demo

### Try Different Task/Agent Combinations

```bash
# Ops triage agent on log monitoring
python demo.py --task log_stream_monitor --agent ops_triage_agent

# Rate limit agent on rate limited API
python demo.py --task rate_limited_api --agent rate_limit_agent
```

### Add Your Own Agent

1. Create a new file in `agents/my_agent.py`
2. Implement the agent interface (see `agents/toy_agent.py` for template)
3. Run: `python demo.py --task <task_name> --agent my_agent`

### Add Your Own Task

1. Create a new directory in `tasks/my_task/`
2. Add required files: `setup.py`, `actions.py`, `validate.py`, `task.toml`
3. Run: `python demo.py --task my_task --agent <agent_name>`

## Architecture

```
┌─────────────┐
│   demo.py   │  ← Entry point
└──────┬──────┘
       │
       ├─→ Load Task (from tasks/)
       │   └─→ setup.py, actions.py, validate.py
       │
       ├─→ Load Agent (from agents/)
       │   └─→ Agent class with reset/observe/act
       │
       └─→ Run Episode (agent_bench.runner)
           └─→ Episode loop until completion
```

## Next Steps

- Explore the [Agent Interface Documentation](../../docs/agent_interface.md)
- Read about [Task Creation](../../docs/tasks.md)
- Check out [Advanced Agent Examples](../../agents/README.md)
- Learn about [Baseline Comparison](../../docs/baseline.md)
