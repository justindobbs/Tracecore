#!/usr/bin/env sh

agent-bench run \
  --agent agents/toy_agent.py \
  --task filesystem_hidden_config@1 \
  --seed 42
