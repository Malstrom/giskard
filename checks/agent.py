"""
checks/agent.py — zeroth laws: agent manifest

Validates .agent.yml structure and required blocks.
These checks are framework-agnostic.
"""

from pathlib import Path
from core import run_check, Report

CHECKS = [
    {
        "label": ".agent.yml is valid YAML",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "connector_check",
        "rule": "agent.yml",
    },
    {
        "label": "connector_check is the first block",
        "proxy": "yaml_first_key",
        "file": ".agent.yml",
        "expected": "connector_check",
        "rule": "agent.yml",
    },
    {
        "label": "global block present",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "global",
        "rule": "agent.yml",
    },
    {
        "label": "repo_map block present",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "repo_map",
        "rule": "agent.yml",
    },
    {
        "label": "file_access block present",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "file_access",
        "rule": "agent.yml",
    },
    {
        "label": "tool_approval block present",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "tool_approval",
        "rule": "agent.yml",
    },
    {
        "label": "handlers block present",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "handlers",
        "rule": "agent.yml",
    },
    {
        "label": "post_action_hook block present",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "post_action_hook",
        "rule": "agent.yml",
    },
    {
        "label": "global.language declared",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "global",
        "rule": "agent.yml",
    },
    {
        "label": "global.replies_in absent (forbidden field)",
        "proxy": "yaml_key_absent",
        "file": ".agent.yml",
        "key": "global.replies_in",
        "rule": "agent.yml",
    },
    {
        "label": "post_action_hook.after_every_state_change present",
        "proxy": "yaml_subkeys_exist",
        "file": ".agent.yml",
        "key": "post_action_hook",
        "required_subkeys": ["after_every_state_change"],
        "rule": "agent.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("zeroth — agent")
    for check in CHECKS:
        run_check(repo, check, report)
