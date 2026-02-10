"""Environment abstraction (stub)."""

class Environment:
    def __init__(self):
        self.hidden_state = {}

    def set_hidden_state(self, key, value):
        self.hidden_state[key] = value

    def get_hidden_state(self, key, default=None):
        return self.hidden_state.get(key, default)
