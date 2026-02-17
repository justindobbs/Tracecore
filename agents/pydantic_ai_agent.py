"""Reference pydantic-ai agent for filesystem tasks.

This agent demonstrates how to use pydantic-ai with TraceCore's deterministic
episode runtime. It targets the filesystem_hidden_config@1 task.

Usage:
    agent-bench run --agent agents/pydantic_ai_agent.py --task filesystem_hidden_config@1 --seed 42

Requirements:
    pip install -e ".[pydantic]"
    export OPENAI_API_KEY=your-key-here  # or use another provider
"""

from agent_bench.integrations.pydantic_ai import PydanticAIAgent, filesystem_tools

SYSTEM_PROMPT = """You are an agent solving filesystem exploration tasks.

Your goal is to find and extract the API_KEY value from hidden configuration files.

Available tools:
- list_dir(path): List files in a directory
- read_file(path): Read contents of a file
- extract_value(content, key): Extract a key-value pair from content (format: KEY=value)
- set_output(key, value): Set the final output (call this once you find the API_KEY)

Strategy:
1. Start by listing the /app directory to see what files are available
2. Read files that look like configuration files (especially hidden files starting with .)
3. When you find a file with API_KEY=<value>, extract the value
4. Set the output with set_output("API_KEY", value)

Budget constraints:
- You have 200 steps and 40 tool calls maximum
- Plan efficiently to avoid wasting budget

Important:
- Hidden config files often start with a dot (.) and may have random suffixes
- The API_KEY format is: API_KEY=<value> on a single line
- Call set_output exactly once when you have the correct value
"""


class FilesystemPydanticAgent(PydanticAIAgent):
    """Pydantic-AI agent for filesystem exploration tasks."""

    def __init__(self):
        """Initialize the agent with OpenAI GPT-4o-mini model.
        
        To use a different model, change the model string:
        - OpenAI: "openai:gpt-4o-mini", "openai:gpt-4o"
        - Anthropic: "anthropic:claude-3-5-sonnet-20241022"
        - Local: "ollama:llama3.2" (requires Ollama running)
        """
        super().__init__(
            model="openai:gpt-4o-mini",
            tools=filesystem_tools,
            system_prompt=SYSTEM_PROMPT,
        )
