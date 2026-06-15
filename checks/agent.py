"""
checks/agent.py — zeroth laws: agent manifest

Validates .agent.yml structure against the canonical block spec.
See: https://github.com/Malstrom/zeroth/issues/100
These checks are framework-agnostic.
"""

import logging
from pathlib import Path

import urllib.request
import urllib.error

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

from core import run_check, Report

log = logging.getLogger(__name__)

VALID_ACCESS = ["read-only", "read-write", "append-only", "write-once"]

# ---------------------------------------------------------------------------
# Fallback — used when zeroth is unreachable (network error, rate limit, etc.)
# ---------------------------------------------------------------------------
_SCENARIOS_REQUIRED_SUBKEYS_FALLBACK = ["file", "spec", "read_before_responding", "on_no_match"]

_ZEROTH_RULES_AGENT_URL = (
    "https://raw.githubusercontent.com/Malstrom/zeroth/main/rules/agent.yml"
)


def _fetch_scenarios_required_subkeys() -> list[str]:
    """Fetch rules/agent.yml from zeroth and derive scenarios.required_fields.

    Returns the list of required subkeys for the `scenarios` block.
    Falls back to ``_SCENARIOS_REQUIRED_SUBKEYS_FALLBACK`` on any error.
    """
    if yaml is None:  # pragma: no cover
        log.warning(
            "PyYAML not available — using fallback scenarios subkeys: %s",
            _SCENARIOS_REQUIRED_SUBKEYS_FALLBACK,
        )
        return _SCENARIOS_REQUIRED_SUBKEYS_FALLBACK

    try:
        with urllib.request.urlopen(_ZEROTH_RULES_AGENT_URL, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as exc:
        log.warning(
            "Could not fetch zeroth rules/agent.yml (%s) — using fallback subkeys: %s",
            exc,
            _SCENARIOS_REQUIRED_SUBKEYS_FALLBACK,
        )
        return _SCENARIOS_REQUIRED_SUBKEYS_FALLBACK

    try:
        rules = yaml.safe_load(raw)
        subkeys = rules["scenarios"]["required_fields"]
        if not isinstance(subkeys, list) or not subkeys:
            raise ValueError(f"unexpected required_fields value: {subkeys!r}")
        log.debug("scenarios.required_subkeys inferred from zeroth: %s", subkeys)
        return subkeys
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Failed to parse zeroth rules/agent.yml (%s) — using fallback subkeys: %s",
            exc,
            _SCENARIOS_REQUIRED_SUBKEYS_FALLBACK,
        )
        return _SCENARIOS_REQUIRED_SUBKEYS_FALLBACK


# Resolved once at module load — stable for the lifetime of the process.
_SCENARIOS_REQUIRED_SUBKEYS: list[str] = _fetch_scenarios_required_subkeys()


CHECKS = [
    # ---------------------------------------------------------------------------
    # YAML parseable — use presence of 'language' block as proxy
    # ---------------------------------------------------------------------------
    {
        "label": ".agent.yml is valid YAML with language block",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "language",
        "rule": "agent.yml",
    },

    # ---------------------------------------------------------------------------
    # Mandatory block order — first block must be language
    # ---------------------------------------------------------------------------
    {
        "label": "language is the first block",
        "proxy": "yaml_first_key",
        "file": ".agent.yml",
        "expected": "language",
        "rule": "agent.yml",
    },

    # ---------------------------------------------------------------------------
    # Mandatory blocks present
    # ---------------------------------------------------------------------------
    {
        "label": "work_rules block present",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "work_rules",
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
        "label": "scenarios block present",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "scenarios",
        "rule": "agent.yml",
    },
    {
        "label": "workspace block present",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "workspace",
        "rule": "agent.yml",
    },

    # ---------------------------------------------------------------------------
    # language subkeys
    # ---------------------------------------------------------------------------
    {
        "label": "language.chat declared",
        "proxy": "yaml_subkeys_exist",
        "file": ".agent.yml",
        "key": "language",
        "required_subkeys": ["chat"],
        "rule": "agent.yml",
    },
    {
        "label": "language.files == english",
        "proxy": "yaml_key_equals",
        "file": ".agent.yml",
        "key": "language.files",
        "expected": "english",
        "rule": "agent.yml",
    },
    {
        "label": "language.filenames == english",
        "proxy": "yaml_key_equals",
        "file": ".agent.yml",
        "key": "language.filenames",
        "expected": "english",
        "rule": "agent.yml",
    },

    # ---------------------------------------------------------------------------
    # work_rules subkeys
    # ---------------------------------------------------------------------------
    {
        "label": "work_rules has required keys",
        "proxy": "yaml_subkeys_exist",
        "file": ".agent.yml",
        "key": "work_rules",
        "required_subkeys": [
            "branch_per_issue",
            "branch_naming",
            "all_writes_via_pr",
            "merge_strategy",
        ],
        "rule": "agent.yml",
    },

    # ---------------------------------------------------------------------------
    # tool_approval — all keys must be present
    # ---------------------------------------------------------------------------
    {
        "label": "tool_approval has all required keys",
        "proxy": "yaml_subkeys_exist",
        "file": ".agent.yml",
        "key": "tool_approval",
        "required_subkeys": [
            "create_branch",
            "push_files",
            "create_pr",
            "create_issue",
            "create_sub_issue",
            "update_issue",
            "merge_to_main",
            "delete_file",
            "destructive_ops",
        ],
        "rule": "agent.yml",
    },
    {
        "label": "tool_approval.delete_file == true",
        "proxy": "yaml_key_equals",
        "file": ".agent.yml",
        "key": "tool_approval.delete_file",
        "expected": True,
        "rule": "agent.yml",
    },
    {
        "label": "tool_approval.destructive_ops == true",
        "proxy": "yaml_key_equals",
        "file": ".agent.yml",
        "key": "tool_approval.destructive_ops",
        "expected": True,
        "rule": "agent.yml",
    },

    # ---------------------------------------------------------------------------
    # scenarios subkeys
    # required_subkeys are inferred at runtime from zeroth/rules/agent.yml
    # (scenarios.required_fields). Fallback to hardcoded list on fetch failure.
    # ---------------------------------------------------------------------------
    {
        "label": "scenarios has required keys",
        "proxy": "yaml_subkeys_exist",
        "file": ".agent.yml",
        "key": "scenarios",
        "required_subkeys": _SCENARIOS_REQUIRED_SUBKEYS,
        "rule": "agent.yml",
    },
    {
        "label": "scenarios.read_before_responding == true",
        "proxy": "yaml_key_equals",
        "file": ".agent.yml",
        "key": "scenarios.read_before_responding",
        "expected": True,
        "rule": "agent.yml",
    },

    # ---------------------------------------------------------------------------
    # workspace — mandatory entries
    # ---------------------------------------------------------------------------
    {
        "label": "workspace declares .scenarios.yml",
        "proxy": "yaml_key_exists",
        "file": ".agent.yml",
        "key": "workspace",
        "rule": "agent.yml",
    },

    # ---------------------------------------------------------------------------
    # Forbidden blocks — fail if present
    # ---------------------------------------------------------------------------
    {
        "label": "connector_check absent (forbidden)",
        "proxy": "yaml_key_absent",
        "file": ".agent.yml",
        "key": "connector_check",
        "rule": "agent.yml",
    },
    {
        "label": "global absent (forbidden)",
        "proxy": "yaml_key_absent",
        "file": ".agent.yml",
        "key": "global",
        "rule": "agent.yml",
    },
    {
        "label": "handlers absent (forbidden)",
        "proxy": "yaml_key_absent",
        "file": ".agent.yml",
        "key": "handlers",
        "rule": "agent.yml",
    },
    {
        "label": "post_action_hook absent (forbidden)",
        "proxy": "yaml_key_absent",
        "file": ".agent.yml",
        "key": "post_action_hook",
        "rule": "agent.yml",
    },
    {
        "label": "repo_map absent (forbidden)",
        "proxy": "yaml_key_absent",
        "file": ".agent.yml",
        "key": "repo_map",
        "rule": "agent.yml",
    },
    {
        "label": "file_access absent (forbidden)",
        "proxy": "yaml_key_absent",
        "file": ".agent.yml",
        "key": "file_access",
        "rule": "agent.yml",
    },
    {
        "label": "write_ahead absent (forbidden)",
        "proxy": "yaml_key_absent",
        "file": ".agent.yml",
        "key": "write_ahead",
        "rule": "agent.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("zeroth — agent")
    for check in CHECKS:
        run_check(repo, check, report)
