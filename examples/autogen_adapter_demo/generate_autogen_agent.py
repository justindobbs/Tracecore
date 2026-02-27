from agent_bench.integrations.autogen_adapter import generate_agent


def main() -> None:
    generate_agent(
        task_ref="rate_limited_api@1",
        model="gpt-5-nano",
        agents=[
            {
                "name": "Worker",
                "system_message": "Execute tools precisely. Output one JSON action then say DONE.",
            },
            {
                "name": "Supervisor",
                "system_message": "Review the action. Correct if wrong. Say DONE.",
            },
        ],
        output_path="agents/autogen_rate_limit_agent.py",
    )


if __name__ == "__main__":
    main()

