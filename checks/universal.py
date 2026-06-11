"""
checks/universal.py — layer 1: universal zeroth rules.

Aggregates all checks that run on every repo regardless of framework.
Framework-specific checks live in checks/frameworks/{name}.py (layer 2).

Modules:
  files       — required files presence (.agent.yml, .scenarios.yml, etc.)
  agent       — .agent.yml structure and constraints
  scenarios   — .scenarios.yml required scenarios
  connections — external connections and tool approval levels
"""

from pathlib import Path
from core import Report
from checks import files, agent, scenarios, connections


def run(repo: Path, report: Report) -> None:
    files.run(repo, report)
    agent.run(repo, report)
    scenarios.run(repo, report)
    connections.run(repo, report)
