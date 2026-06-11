"""
checks/connections.py — zeroth laws: connection registry

Validates .registry.yml top-level fields and per-connection structure.
These checks are framework-agnostic.
"""

import yaml
from pathlib import Path
from core import run_check, Report, _gh_annotation

CHECKS = [
    {
        "label": ".registry.yml missing 'framework' field",
        "proxy": "yaml_key_exists",
        "file": ".registry.yml",
        "key": "framework",
        "rule": "connections.yml",
    },
    {
        "label": ".registry.yml missing 'version' field",
        "proxy": "yaml_key_exists",
        "file": ".registry.yml",
        "key": "version",
        "rule": "connections.yml",
    },
    {
        "label": ".registry.yml missing 'connections' field",
        "proxy": "yaml_key_exists",
        "file": ".registry.yml",
        "key": "connections",
        "rule": "connections.yml",
    },
]


def _check_connection_entries(repo: Path, report: Report) -> None:
    """Validates each entry in connections[] has required fields."""
    registry_path = repo / ".registry.yml"
    if not registry_path.exists():
        return
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return

    connections = data.get("connections")
    if not isinstance(connections, list) or not connections:
        report.add("connections list is empty or missing", None, "no connections to validate")
        return

    errors = []
    for i, conn in enumerate(connections):
        if not isinstance(conn, dict):
            errors.append(f"connection[{i}] is not a mapping")
            continue
        for field in ("repo", "role", "access"):
            if not conn.get(field):
                errors.append(f"connection[{i}] missing '{field}'")
        trigger = conn.get("sync_trigger")
        if trigger is not None and (not isinstance(trigger, list) or len(trigger) == 0):
            errors.append(f"connection[{i}] sync_trigger is present but empty")

    if errors:
        for msg in errors:
            report.add(msg, False, rule="connections.yml")
            _gh_annotation("error", f"giskard ERROR: {msg}", ".registry.yml")
    else:
        report.add(f"all {len(connections)} connection(s) valid", True)


def run(repo: Path, report: Report) -> None:
    report.section("zeroth — connections")
    for check in CHECKS:
        run_check(repo, check, report)
    _check_connection_entries(repo, report)
