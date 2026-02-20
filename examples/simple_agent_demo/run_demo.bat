@echo off
REM Quick launcher for the simple agent demo (Windows)

echo 🎯 TraceCore Simple Agent Demo Launcher
echo.

if "%1"=="" (
    echo Available demos:
    echo.
    echo   1. Dice Game ^(simple, deterministic^)
    echo   2. Rate Limited Chain ^(complex, API interactions^)
    echo   3. List all tasks
    echo   4. List all agents
    echo.
    set /p choice="Select a demo (1-4): "
    
    if "!choice!"=="1" (
        python demo.py --task dice_game --agent dice_game_agent
    ) else if "!choice!"=="2" (
        python demo.py --task rate_limited_chain --agent chain_agent --verbose
    ) else if "!choice!"=="3" (
        python demo.py --list-tasks
    ) else if "!choice!"=="4" (
        python demo.py --list-agents
    ) else (
        echo Invalid choice
        exit /b 1
    )
) else (
    REM Pass through arguments
    python demo.py %*
)
