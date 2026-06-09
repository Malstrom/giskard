#!/usr/bin/env python3
"""
giskard — generic framework validator for the Malstrom ecosystem.

Loads a checklist.yml from zeroth for the given framework and runs
every check using the PROXY_REGISTRY. Zero framework-specific logic here.

Usage:
  python giskard.py --framework dojo --repo /path/to/repo
  python giskard.py --framework tensho --repo /path/to/repo
  python giskard.py --framework dojo --repo /path/to/repo --zeroth-ref v1.2.0
  python giskard.py --framework dojo --repo /path/to/repo --zeroth-ref abc1234
"""

import argparse
import re
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path

ZEROTH_BASE_TEMPLATE = "https://raw.githubusercontent.com/Malstrom/zeroth/{ref}/frameworks"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_checklist(framework: str, zeroth_ref: str = "main") -> dict:
    import urllib.request
    base = ZEROTH_BASE_TEMPLATE.format(ref=zeroth_ref)
    url = f"{base}/{framework}/checklist.yml"
    try:
        with urllib.request.urlopen(url) as r:
            return yaml.safe_load(r.read().decode()) or {}
    except Exception as e:
        print(f"[giskard] ERROR: cannot load checklist for '{framework}' at ref '{zeroth_ref}': {e}")
        sys.exit(1)


def _fetch_url(url: str) -> str:
    import urllib.request
    try:
        with urllib.request.urlopen(url) as r:
            return r.read().decode()
    except Exception:
        return ""


def _read_file(repo: Path, filename: str) -> str:
    p = repo / filename
    return p.read_text() if p.exists() else ""


def _parse_yaml(repo: Path, filename: str) -> dict:
    content = _read_file(repo, filename)
    if not content:
        return {}
    try:
        parsed = yaml.safe_load(content)
        return parsed if isinstance(parsed, dict) else {}
    except yaml.YAMLError:
        return {}


# ---------------------------------------------------------------------------
# Proxy implementations
# ---------------------------------------------------------------------------

def proxy_file_exists(repo: Path, check: dict) -> tuple:
    target = check["target"]
    must_exist = check.get("must_exist", True)
    path = repo / target
    result = path.exists() == must_exist
    return result, ""


def proxy_dir_has_subfolders(repo: Path, check: dict) -> tuple:
    target = repo / check["target"].rstrip("/")
    if not target.is_dir():
        return False, ""
    subs = [d for d in target.iterdir() if d.is_dir()]
    return len(subs) > 0, f"{len(subs)} subfolder(s) found"


def proxy_dir_has_templates(repo: Path, check: dict) -> tuple:
    target = repo / check["target"].rstrip("/")
    if not target.is_dir():
        return False, ""
    required = check.get("required_files", [])
    missing = [f for f in required if not (target / f).exists()]
    if missing:
        print(f"    missing templates: {', '.join(missing)}")
    return len(missing) == 0, ""


def proxy_template_matches_zeroth(repo: Path, check: dict) -> tuple:
    """Fetch template from zeroth and compare with repo's copy. Exact match required."""
    framework = check["framework"]
    template = check["template"]
    zeroth_ref = check.get("zeroth_ref", "main")
    base = ZEROTH_BASE_TEMPLATE.format(ref=zeroth_ref)
    zeroth_url = f"{base}/{framework}/templates/{template}"
    zeroth_content = _fetch_url(zeroth_url)
    if not zeroth_content:
        return None, f"could not fetch {zeroth_url}"
    repo_content = _read_file(repo, f"templates/{template}")
    if not repo_content:
        return False, "template missing in repo"
    match = zeroth_content.strip() == repo_content.strip()
    if not match:
        print(f"    {template}: repo differs from zeroth")
    return match, f"zeroth: {len(zeroth_content)} chars, repo: {len(repo_content)} chars"


def proxy_yaml_key_exists(repo: Path, check: dict) -> tuple:
    parsed = _parse_yaml(repo, check["file"])
    key = check["key"]
    return key in parsed, ""


def proxy_yaml_key_equals(repo: Path, check: dict) -> tuple:
    parsed = _parse_yaml(repo, check["file"])
    keys = check["key"].split(".")
    val = parsed
    for k in keys:
        if not isinstance(val, dict):
            return False, ""
        val = val.get(k)
    result = val == check["expected"]
    return result, f"got '{val}', expected '{check['expected']}'"


def proxy_yaml_key_contains(repo: Path, check: dict) -> tuple:
    parsed = _parse_yaml(repo, check["file"])
    keys = check["key"].split(".")
    val = parsed
    for k in keys:
        if not isinstance(val, dict):
            return False, ""
        val = val.get(k)
    result = check["contains"] in str(val or "")
    return result, ""


def proxy_yaml_first_key(repo: Path, check: dict) -> tuple:
    content = _read_file(repo, check["file"])
    lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
    first_key = lines[0].split(":")[0].strip() if lines else ""
    result = first_key == check["expected"]
    return result, f"first key is '{first_key}'"


def proxy_yaml_levels_valid(repo: Path, check: dict) -> tuple:
    parsed = _parse_yaml(repo, check["file"])
    keys = check["key"].split(".")
    val = parsed
    for k in keys:
        val = (val or {}).get(k)
    if not isinstance(val, dict):
        return None, "field missing or not a map"
    allowed = set(check["allowed"])
    bad = [v for v in val.values() if v not in allowed]
    if bad:
        print(f"    invalid values: {bad}")
    return len(bad) == 0, ""


def proxy_yaml_subkeys_exist(repo: Path, check: dict) -> tuple:
    parsed = _parse_yaml(repo, check["file"])
    keys = check["key"].split(".")
    val = parsed
    for k in keys:
        if not isinstance(val, dict):
            return False, ""
        val = val.get(k)
    if not isinstance(val, dict):
        return False, ""
    required = check.get("required_subkeys", [])
    missing = [k for k in required if k not in val]
    if missing:
        print(f"    missing subkeys: {missing}")
    return len(missing) == 0, ""


def proxy_scenario_present(repo: Path, check: dict) -> tuple:
    sc = _parse_yaml(repo, ".scenarios.yml")
    rs = sc.get("required_scenarios", {})
    name = check["scenario"]
    present = name in (rs or {})
    return present, ""


def proxy_scenario_last(repo: Path, check: dict) -> tuple:
    sc = _parse_yaml(repo, ".scenarios.yml")
    rs = sc.get("required_scenarios", {}) or {}
    name = check["scenario"]
    keys = list(rs.keys())
    result = keys[-1] == name if keys else False
    return result, f"last is '{keys[-1] if keys else 'none'}'"


def proxy_scenario_not_present(repo: Path, check: dict) -> tuple:
    sc = _parse_yaml(repo, ".scenarios.yml")
    rs = sc.get("required_scenarios", {}) or {}
    name = check["scenario"]
    return name not in rs, ""


def proxy_scenario_input_sources(repo: Path, check: dict) -> tuple:
    sc = _parse_yaml(repo, ".scenarios.yml")
    rs = sc.get("required_scenarios", {}) or {}
    name = check["scenario"]
    if name not in rs:
        return False, "scenario not found"
    actual = len((rs[name] or {}).get("input_sources", []))
    expected = check["min_count"]
    return actual >= expected, f"{actual}/{expected} input_sources"


def proxy_handler_present(repo: Path, check: dict) -> tuple:
    parsed = _parse_yaml(repo, ".agent.yml")
    h = parsed.get("handlers", {}) or {}
    name = check["handler"]
    return name in h, ""


def proxy_handler_has_key(repo: Path, check: dict) -> tuple:
    parsed = _parse_yaml(repo, ".agent.yml")
    h = (parsed.get("handlers", {}) or {}).get(check["handler"], {}) or {}
    return check["key"] in h, ""


def proxy_text_search(repo: Path, check: dict) -> tuple:
    content = _read_file(repo, check["file"])
    terms = check["terms"]
    missing = [t for t in terms if t not in content]
    if missing:
        print(f"    missing terms: {missing}")
    return len(missing) == 0, f"searched in {check['file']}"


def proxy_token_count(repo: Path, check: dict) -> tuple:
    content = _read_file(repo, check["file"])
    token = check["token"]
    count = content.count(token)
    expected = check["expected"]
    if count != expected:
        print(f"    found {count} '{token}' tokens, expected {expected}")
    return count == expected, f"{count}/{expected} tokens"


def proxy_file_access_mode(repo: Path, check: dict) -> tuple:
    """
    Supports two file_access structures in .agent.yml:

    1. List-based (preferred):
       file_access:
         read:   [...]          # optional — coexistence with append is fine
         append: ["kiroku/nikki/**"]
         write:  [...]

       Pass if: pattern is in file_access[mode] AND NOT in write
       (being also in read is acceptable for append-mode patterns)

    2. Flat (legacy):
       file_access:
         "kiroku/nikki/**": append-only

       Pass if: value string contains the mode word.
    """
    parsed = _parse_yaml(repo, ".agent.yml")
    fa = parsed.get("file_access", {}) or {}
    pattern = check["pattern"]
    mode = check["mode"].lower()

    # --- list-based structure ---
    all_modes = {k: v for k, v in fa.items() if isinstance(v, list)}
    if all_modes:
        in_correct = pattern in (all_modes.get(mode) or [])
        # Only fail if pattern appears in write (destructive), not if it's also in read
        in_write = pattern in (all_modes.get("write") or [])
        if not in_correct:
            print(f"    '{pattern}' not found in file_access.{mode}")
        if in_write:
            print(f"    '{pattern}' is also in file_access.write — must not be writable")
        return in_correct and not in_write, ""

    # --- flat / legacy structure ---
    val = str(fa.get(pattern, "")).lower()
    return mode in val, ""


def proxy_write_ahead_rule(repo: Path, check: dict) -> tuple:
    content = _read_file(repo, ".agent.yml")
    return check["contains"] in content, ""


# ---------------------------------------------------------------------------
# Proxy registry
# ---------------------------------------------------------------------------

PROXY_REGISTRY = {
    "file_exists": proxy_file_exists,
    "dir_has_subfolders": proxy_dir_has_subfolders,
    "dir_has_templates": proxy_dir_has_templates,
    "template_matches_zeroth": proxy_template_matches_zeroth,
    "yaml_key_exists": proxy_yaml_key_exists,
    "yaml_key_equals": proxy_yaml_key_equals,
    "yaml_key_contains": proxy_yaml_key_contains,
    "yaml_first_key": proxy_yaml_first_key,
    "yaml_levels_valid": proxy_yaml_levels_valid,
    "yaml_subkeys_exist": proxy_yaml_subkeys_exist,
    "scenario_present": proxy_scenario_present,
    "scenario_last": proxy_scenario_last,
    "scenario_not_present": proxy_scenario_not_present,
    "scenario_input_sources": proxy_scenario_input_sources,
    "handler_present": proxy_handler_present,
    "handler_has_key": proxy_handler_has_key,
    "text_search": proxy_text_search,
    "token_count": proxy_token_count,
    "file_access_mode": proxy_file_access_mode,
    "write_ahead_rule": proxy_write_ahead_rule,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class Report:
    def __init__(self, framework: str, repo: Path, zeroth_ref: str = "main"):
        self.framework = framework
        self.repo = repo
        self.zeroth_ref = zeroth_ref
        self.lines = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def add(self, label: str, result, note: str = ""):
        if result is True:
            self.passed += 1
            icon = "✅"
        elif result is False:
            self.failed += 1
            icon = "❌"
        else:
            self.skipped += 1
            icon = "⚠️"
        suffix = f" — {note}" if note else ""
        line = f"  {icon} {label}{suffix}"
        print(line)
        self.lines.append(line)

    def section(self, name: str):
        line = f"\n\u2502 {name}"
        print(line)
        self.lines.append(line)

    def save(self):
        out = self.repo / "giskard-report.md"
        status = "✅ passed" if self.failed == 0 else "❌ failed"
        header = [
            "# giskard report",
            "",
            f"- **framework**: {self.framework}",
            f"- **repo**: {self.repo.name}",
            f"- **zeroth-ref**: {self.zeroth_ref}",
            f"- **date**: {self.ts}",
            f"- **result**: {status} — {self.passed} passed / {self.failed} failed / {self.skipped} skipped",
            "",
            "## checks",
            "",
        ]
        with open(out, "w") as f:
            f.write("\n".join(header) + "\n")
            f.write("\n".join(self.lines) + "\n")
        print(f"\n[giskard] report written to {out}")


def run_check(repo: Path, check: dict, report: Report):
    label = check.get("label", str(check))
    proxy_name = check.get("proxy")
    if not proxy_name:
        report.add(label, None, "no proxy defined")
        return
    fn = PROXY_REGISTRY.get(proxy_name)
    if not fn:
        report.add(label, None, f"unknown proxy '{proxy_name}'")
        return
    try:
        result, note = fn(repo, check)
        report.add(label, result, note)
    except Exception as e:
        report.add(label, False, f"exception: {e}")


def run_section(repo: Path, section_name: str, checks, report: Report):
    report.section(section_name)
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict):
                run_check(repo, check, report)
            else:
                report.add(str(check), None, "malformed check")
    elif isinstance(checks, dict):
        for subsection, sub_checks in checks.items():
            report.section(f"{section_name} / {subsection}")
            for check in (sub_checks or []):
                if isinstance(check, dict):
                    run_check(repo, check, report)
                else:
                    report.add(str(check), None, "malformed check")


def run(framework: str, repo_path: str, zeroth_ref: str = "main"):
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        print(f"[giskard] ERROR: repo path not found: {repo}")
        sys.exit(1)

    print(f"[giskard] validating '{repo.name}' as framework: {framework}")
    print(f"[giskard] zeroth ref: {zeroth_ref}")
    print(f"[giskard] loading checklist from zeroth...")
    checklist = load_checklist(framework, zeroth_ref)

    report = Report(framework, repo, zeroth_ref)

    for section_name, checks in checklist.items():
        run_section(repo, section_name, checks, report)

    print(f"\n[giskard] result: {report.passed} passed / {report.failed} failed / {report.skipped} skipped")
    report.save()

    if report.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="giskard — Malstrom framework validator")
    parser.add_argument("--framework", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument(
        "--zeroth-ref",
        default="main",
        dest="zeroth_ref",
        help="Git ref (tag, SHA, branch) for zeroth checklist. Default: main.",
    )
    args = parser.parse_args()
    run(args.framework, args.repo, args.zeroth_ref)
