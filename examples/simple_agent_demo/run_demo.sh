#!/bin/bash
# Quick launcher for the simple agent demo

echo "🎯 TraceCore Simple Agent Demo Launcher"
echo ""

# Check if arguments provided
if [ $# -eq 0 ]; then
    echo "Available demos:"
    echo ""
    echo "  1. Dice Game (simple, deterministic)"
    echo "  2. Rate Limited Chain (complex, API interactions)"
    echo "  3. List all tasks"
    echo "  4. List all agents"
    echo ""
    read -p "Select a demo (1-4): " choice
    
    case $choice in
        1)
            python demo.py --task dice_game --agent dice_game_agent
            ;;
        2)
            python demo.py --task rate_limited_chain --agent chain_agent --verbose
            ;;
        3)
            python demo.py --list-tasks
            ;;
        4)
            python demo.py --list-agents
            ;;
        *)
            echo "Invalid choice"
            exit 1
            ;;
    esac
else
    # Pass through arguments
    python demo.py "$@"
fi
