"""Test deterministic dice game agent without API calls."""
import random
from agents.dice_game_agent import Agent, RANDOM_SEED


def test_deterministic_rolling():
    """Verify that seeded random produces consistent results."""
    agent = Agent()
    agent.reset(None)

    # First run
    rolls_1 = []
    for _ in range(10):
        action = agent.act()
        rolls_1.append(action["args"]["result"])

    # Reset and run again
    agent.reset(None)
    rolls_2 = []
    for _ in range(10):
        action = agent.act()
        rolls_2.append(action["args"]["result"])

    # Should be identical
    assert rolls_1 == rolls_2, f"Rolls should match: {rolls_1} != {rolls_2}"
    print(f"✓ Deterministic rolling verified: {rolls_1}")


def test_incremental_seeding():
    """Verify that each roll uses incrementing seed."""
    agent = Agent()
    agent.reset(None)

    rolls = []
    for i in range(5):
        random.seed(RANDOM_SEED + i)
        expected = random.randint(1, 6)
        action = agent.act()
        actual = action["args"]["result"]
        assert actual == expected, f"Roll {i}: expected {expected}, got {actual}"
        rolls.append(actual)

    print(f"✓ Incremental seeding verified: {rolls}")


def test_agent_interface():
    """Verify TraceCore agent interface works."""
    agent = Agent()

    # Test reset
    agent.reset({"test": "spec"})
    assert agent.task == {"test": "spec"}
    assert agent.memory["roll_count"] == 0

    # Test observe
    observation = {"visible_state": {"files_seen": []}}
    agent.observe(observation)
    assert agent.obs == observation

    # Test act
    action = agent.act()
    assert action["type"] == "roll_dice"
    assert "result" in action["args"]
    assert 1 <= action["args"]["result"] <= 6

    print(f"✓ Agent interface verified")


if __name__ == "__main__":
    test_deterministic_rolling()
    test_incremental_seeding()
    test_agent_interface()
    print("\n✅ All tests passed!")
