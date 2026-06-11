"""
checks/frameworks/aurora.py — aurora framework-specific checks (layer 2)

Runs after universal rules (layer 1). Validates aurora-specific structure:
- Required files and directories
- .aurora.yml structure
- templates/ completeness
- handler reindex_check
- session_start reads .aurora.yml
"""

from pathlib import Path
from core import run_check, Report

REQUIRED_TEMPLATES = [
    "inbox.yml",
    "log.yml",
    "log_index.yml",
    "contact.yml",
    "client_context.yml",
    "playbook.yml",
]

CHECKS = [
    # --- required aurora files and directories ---
    {
        "label": ".aurora.yml exists",
        "proxy": "file_exists",
        "target": ".aurora.yml",
        "file": ".aurora.yml",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "clients/ directory exists",
        "proxy": "file_exists",
        "target": "clients",
        "file": "clients/",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "contacts/ directory exists",
        "proxy": "file_exists",
        "target": "contacts",
        "file": "contacts/",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "log/ directory exists",
        "proxy": "file_exists",
        "target": "log",
        "file": "log/",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "playbooks/ directory exists",
        "proxy": "file_exists",
        "target": "playbooks",
        "file": "playbooks/",
        "rule": "aurora/structure.yml",
    },

    # --- templates/ completeness ---
    {
        "label": "templates/ has all required aurora templates",
        "proxy": "dir_has_templates",
        "target": "templates",
        "required_files": REQUIRED_TEMPLATES,
        "rule": "aurora/structure.yml",
    },

    # --- .aurora.yml structure ---
    {
        "label": ".aurora.yml has 'version' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "version",
        "rule": "aurora/structure.yml",
    },
    {
        "label": ".aurora.yml has 'owner' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "owner",
        "rule": "aurora/structure.yml",
    },
    {
        "label": ".aurora.yml has 'language' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "language",
        "rule": "aurora/structure.yml",
    },
    {
        "label": ".aurora.yml has 'clients' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "clients",
        "rule": "aurora/structure.yml",
    },
    {
        "label": ".aurora.yml has 'work_types' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "work_types",
        "rule": "aurora/structure.yml",
    },

    # --- handlers ---
    {
        "label": "handler reindex_check present",
        "proxy": "handler_present",
        "handler": "reindex_check",
        "file": ".agent.yml",
        "rule": "aurora/structure.yml",
    },

    # --- session_start reads .aurora.yml ---
    {
        "label": "session_start reads .aurora.yml",
        "proxy": "scenario_input_sources",
        "scenario": "session_start",
        "min_count": 1,
        "rule": "aurora/structure.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("aurora")
    for check in CHECKS:
        run_check(repo, check, report)
