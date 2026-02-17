"""Test dice game agent with Pydantic AI and API calls."""
import os
from agents.dice_game_agent import Agent, run_standalone


def test_pydantic_ai_with_api():
    """Test Pydantic AI agent with actual API calls."""
    # Check if API key is set
    api_key = os.getenv('PYDANTIC_AI_GATEWAY_API_KEY')
    if not api_key:
        print("⚠️  Skipping: PYDANTIC_AI_GATEWAY_API_KEY not set")
        return

    print("Testing Pydantic AI agent with API calls...")
    try:
        run_standalone()
        print("✓ Pydantic AI agent test passed")
    except Exception as e:
        print(f"✗ Pydantic AI agent test failed: {e}")
        raise


def test_agent_with_pydantic_mode():
    """Test agent with Pydantic AI mode enabled."""
    # Check if API key is set
    api_key = os.getenv('PYDANTIC_AI_GATEWAY_API_KEY')
    if not api_key:
        print("⚠️  Skipping: PYDANTIC_AI_GATEWAY_API_KEY not set")
        return

    print("Testing agent with Pydantic AI mode...")
    agent = Agent(use_pydantic_ai=True)
    agent.reset({"test": "spec"})

    # Verify agent has Pydantic AI configured
    assert agent._use_pydantic_ai is True
    assert hasattr(agent, '_pydantic_agent')

    print("✓ Agent with Pydantic AI mode verified")


if __name__ == "__main__":
    test_pydantic_ai_with_api()
    test_agent_with_pydantic_mode()
    print("\n✅ All Pydantic AI tests completed!")
