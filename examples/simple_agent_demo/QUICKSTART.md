# Quick Start Guide

## Run Your First Demo (30 seconds)

```bash
cd examples/simple_agent_demo
python demo.py --task dice_game --agent dice_game_agent
```

You should see output like:
```
============================================================
🎯 TraceCore Agent Demo
============================================================
Task: dice_game
Agent: dice_game_agent
Seed: 0
============================================================

🔧 Loading task metadata...
✓ Task loaded: dice_game
  Description: Simple dice game for testing record mode. Agent must roll a 4 to win.
  Max steps: 3
  Max tool calls: 3

🚀 Starting episode...
------------------------------------------------------------
------------------------------------------------------------

📈 Episode Results:
  Success: True
  Termination: success
  Steps used: 3
  Tool calls used: 3

📊 Metrics:
    steps_used: 3
    tool_calls_used: 3
============================================================
🎉 Episode completed successfully!
============================================================
```

## What Just Happened?

1. **Task Loaded**: The dice_game task was loaded from `tasks/dice_game/`
2. **Agent Initialized**: The dice_game_agent was loaded from `agents/dice_game_agent.py`
3. **Episode Ran**: The agent interacted with the task environment for 3 steps
4. **Success**: The agent successfully rolled a 4 and won the game!

## Try More Examples

### List all available tasks
```bash
python demo.py --list-tasks
```

### List all available agents
```bash
python demo.py --list-agents
```

### Run with verbose output
```bash
python demo.py --task dice_game --agent dice_game_agent --verbose
```

### Try a different seed
```bash
python demo.py --task dice_game --agent dice_game_agent --seed 42
```

### Run a more complex example
```bash
python demo.py --task rate_limited_chain --agent chain_agent --verbose
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the [agents/](../../agents/) directory to see agent implementations
- Check out the [tasks/](../../tasks/) directory to understand task structure
- Create your own agent by copying `agents/toy_agent.py` as a template
