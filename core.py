#!/usr/bin/env python3
"""
core.py — shared internals for giskard.

Contains: proxy registry, Report, run_check, fetch_zeroth_structure.
No CLI, no framework logic, no imports from giskard or checks/.
All modules (checks/*.py, giskard.py) import from here.
"""

import re
import traceback
import yaml
from datetime import datetime, timezone
from pathlib import Path

# Sentinel for proxy execution errors (distinct from False = check failed)
ERROR = "error"

# In-process cache: (framework, ref) -> parsed structure dict
_STRUCTURE_CACHE: dict = {}

ZEROTH_RAW_BASE = "https://raw.githubusercontent.com/Malstrom/zeroth/{ref}/frameworks"


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

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


def _normalize(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines()]


def _fetch_url(url: str) -> str:
    import urllib.request
    try:
        with urllib.request.urlopen(url) as r:
            return r.read().decode()
    except Exception:
        return ""


def _gh_annotation(level: str, message: str, file: str = ""):
    """Print a GitHub Actions workflow command for annotations."""
    if file:
        print(f"::{level} file={file}::{message}")
    else:
        print(f"::{level}::{message}")


def _resolve_template_content(repo: Path, template_path: str, zeroth_ref: str = "main") -> str:
    """
    Resolve a template path to its content.

    If template_path starts with 'frameworks/', it is a zeroth-canonical path
    and must be fetched from raw.githubusercontent.com/Malstrom/zeroth.
    Otherwise it is a local path relative to the repo root.
    """
    if template_path.startswith("frameworks/"):
        url = f"https://raw.githubusercontent.com/Malstrom/zeroth/{zeroth_ref}/{template_path}"
        content = _fetch_url(url)
        if not content:
            print(f"[giskard] WARNING: could not fetch template from zeroth: {url}")
        return content
    else:
        return _read_file(repo, template_path)


# ---------------------------------------------------------------------------
# Zeroth structure fetcher
# ---------------------------------------------------------------------------

def fetch_zeroth_structure(framework: str, ref: str = "main") -> dict:
    """Fetch and parse frameworks/{framework}/structure.yml from zeroth.

    Returns the parsed dict, or {} on any error.
    Result is cached in-process: repeated calls within one giskard run
    cost only one HTTP request per (framework, ref) pair.
    """
    cache_key = (framework, ref)
    if cache_key in _STRUCTURE_CACHE:
        return _STRUCTURE_CACHE[cache_key]

    url = f"{ZEROTH_RAW_BASE.format(ref=ref)}/{framework}/structure.yml"
    raw = _fetch_url(url)
    if not raw:
        print(f"[giskard] WARNING: could not fetch structure.yml for '{framework}' from {url}")
        _STRUCTURE_CACHE[cache_key] = {}
        return {}

    try:
        parsed = yaml.safe_load(raw)
        result = parsed if isinstance(parsed, dict) else {}
    except yaml.YAMLError as e:
        print(f"[giskard] WARNING: structure.yml for '{framework}' is not valid YAML: {e}")
        result = {}

    _STRUCTURE_CACHE[cache_key] = result
    return result


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
    ZEROTH_BASE = "https://raw.githubusercontent.com/Malstrom/zeroth/{ref}/frameworks"
    framework = check["framework"]
    template = check["template"]
    zeroth_ref = check.get("zeroth_ref", "main")
    url = f"{ZEROTH_BASE.format(ref=zeroth_ref)}/{framework}/templates/{template}"
    zeroth_content = _fetch_url(url)
    if not zeroth_content:
        return None, f"could not fetch {url}"
    repo_content = _read_file(repo, f"templates/{template}")
    if not repo_content:
        return False, "template missing in repo"
    zeroth_lines = _normalize(zeroth_content)
    repo_lines = _normalize(repo_content)
    match = zeroth_lines == repo_lines
    if not match:
        diff_count = sum(1 for a, b in zip(zeroth_lines, repo_lines) if a != b)
        length_diff = len(zeroth_lines) - len(repo_lines)
        detail = f"{diff_count} line(s) differ"
        if length_diff != 0:
            detail += f", {abs(length_diff)} line(s) {'extra in zeroth' if length_diff > 0 else 'extra in repo'}"
        return False, detail
    return True, f"{len(zeroth_lines)} lines match"


def proxy_template_keys_match_framework(repo: Path, check: dict) -> tuple:
    """Kept for backward compatibility."""
    framework = check["framework"]
    template = check["template"]
    ref = check.get("ref", "main")
    url = f"https://raw.githubusercontent.com/Malstrom/{framework}/{ref}/templates/{template}"
    canonical_content = _fetch_url(url)
    if not canonical_content:
        return None, f"could not fetch canonical template from {url}"
    try:
        canonical = yaml.safe_load(canonical_content)
        canonical_keys = set(canonical.keys()) if isinstance(canonical, dict) else set()
    except yaml.YAMLError:
        return None, f"canonical template is not valid YAML: {url}"
    if not canonical_keys:
        return None, "canonical template has no root keys — skipped"
    local_path = repo / "templates" / template
    if not local_path.exists():
        return ERROR, f"templates/{template} not found"
    try:
        local = yaml.safe_load(local_path.read_text(encoding="utf-8"))
        local_keys = set(local.keys()) if isinstance(local, dict) else set()
    except yaml.YAMLError:
        return ERROR, f"templates/{template} is not valid YAML"
    missing = canonical_keys - local_keys
    if missing:
        print(f"    missing keys in templates/{template}: {sorted(missing)}")
    return len(missing) == 0, ""


def proxy_generated_files_match_template(repo: Path, check: dict) -> tuple:
    template_path_str = check["template"]
    glob_pattern = check["glob"]
    zeroth_ref = check.get("zeroth_ref", "main")

    # Resolve template content: from zeroth if frameworks/ path, else local.
    template_content = _resolve_template_content(repo, template_path_str, zeroth_ref)
    if not template_content:
        return None, f"{template_path_str} not found — skipped"

    try:
        raw = yaml.safe_load(template_content)
        template_keys = set(raw.keys()) if isinstance(raw, dict) else set()
        # Strip schema-only meta keys that are not present in generated files
        template_keys -= {"_format", "_required", "_optional", "_invariants"}
        # If template uses _required dict, extract its keys instead
        if not template_keys and isinstance(raw, dict) and "_required" in raw:
            required = raw["_required"]
            if isinstance(required, dict):
                template_keys = set(required.keys())
    except yaml.YAMLError:
        return None, f"{template_path_str} is not valid YAML — skipped"

    if not template_keys:
        return None, f"{template_path_str} has no root keys — skipped"

    files = sorted(repo.glob(glob_pattern))
    if not files:
        return None, f"no files found matching {glob_pattern} — skipped"

    violations = []
    for f in files:
        try:
            parsed = yaml.safe_load(f.read_text(encoding="utf-8"))
            file_keys = set(parsed.keys()) if isinstance(parsed, dict) else set()
        except yaml.YAMLError:
            violations.append((str(f.relative_to(repo)), {"<invalid YAML>"}))
            continue
        missing = template_keys - file_keys
        if missing:
            violations.append((str(f.relative_to(repo)), missing))

    if violations:
        for path, missing in violations:
            print(f"    {path}: missing keys {sorted(missing)}")
        return False, f"{len(violations)}/{len(files)} files missing keys"

    return True, f"{len(files)} file(s) checked"


def proxy_yaml_key_exists(repo: Path, check: dict) -> tuple:
    parsed = _parse_yaml(repo, check["file"])
    key = check["key"]
    return key in parsed, ""


def proxy_yaml_key_absent(repo: Path, check: dict) -> tuple:
    parsed = _parse_yaml(repo, check["file"])
    keys = check["key"].split(".")
    val = parsed
    for k in keys:
        if not isinstance(val, dict):
            return True, "parent key absent"
        if k not in val:
            return True, ""
        val = val[k]
    return False, f"forbidden key '{check['key']}' found"


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


def proxy_scenario_no_forbidden_modules(repo: Path, check: dict) -> tuple:
    FORBIDDEN = {"say", "ask", "propose"}
    parsed = _parse_yaml(repo, ".agent.yml")
    handlers = parsed.get("handlers", {}) or {}
    violations = []
    for handler_name, handler_body in handlers.items():
        if not isinstance(handler_body, dict):
            continue
        actions = handler_body.get("actions", []) or []
        for action in actions:
            if isinstance(action, dict):
                keys = set(action.keys()) & FORBIDDEN
                if keys:
                    violations.append(f"{handler_name}: {keys}")
            elif isinstance(action, str) and action in FORBIDDEN:
                violations.append(f"{handler_name}: '{action}'")
    if violations:
        print(f"    forbidden modules in handlers: {violations}")
    return len(violations) == 0, ""


def proxy_scenarios_index_valid(repo: Path, check: dict) -> tuple:
    """
    Validates that a .scenarios.yml uses the index format.

    Index format requirements:
      - root key must be 'scenarios'
      - value must be a non-empty list
      - each entry must have: id (str), triggers (non-empty list), file (str)
    """
    file_path = check.get("file", ".scenarios.yml")
    content = _read_file(repo, file_path)
    if not content:
        return False, f"{file_path} not found or empty"

    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as e:
        return False, f"invalid YAML: {e}"

    if not isinstance(parsed, dict):
        return False, "root is not a mapping"

    if "scenarios" not in parsed:
        root_keys = list(parsed.keys())
        return False, f"root key is '{root_keys[0] if root_keys else '?'}', expected 'scenarios'"

    entries = parsed["scenarios"]
    if not isinstance(entries, list) or len(entries) == 0:
        return False, "'scenarios' must be a non-empty list"

    violations = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            violations.append(f"entry[{i}] is not a mapping")
            continue
        missing_keys = [k for k in ("id", "triggers", "file") if k not in entry]
        if missing_keys:
            entry_id = entry.get("id", f"[{i}]")
            violations.append(f"{entry_id}: missing {missing_keys}")
            continue
        if not isinstance(entry["triggers"], list) or len(entry["triggers"]) == 0:
            violations.append(f"{entry['id']}: 'triggers' must be a non-empty list")

    if violations:
        for v in violations:
            print(f"    {v}")
        return False, f"{len(violations)} entry violation(s)"

    return True, f"{len(entries)} scenario(s) valid"


def proxy_scenarios_index_files_exist(repo: Path, check: dict) -> tuple:
    """
    For each entry in a .scenarios.yml index, verifies that the referenced
    'file' exists.

    Resolution strategy for paths starting with 'frameworks/':
      1. Check locally first (repo / ref_file). This handles the case where
         zeroth itself is the repo under test (e.g. on a PR that adds new
         scenario files — they exist locally but not yet on remote main).
      2. Fall back to raw.githubusercontent.com/Malstrom/zeroth/{zeroth_ref}/
         for instance repos (e.g. daneel_igor) that reference canonical files
         hosted on zeroth.

    All other paths are resolved relative to the local repo root only.
    """
    file_path = check.get("file", ".scenarios.yml")
    zeroth_ref = check.get("zeroth_ref", "main")
    content = _read_file(repo, file_path)
    if not content:
        return None, f"{file_path} not found — skipped"

    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError:
        return None, f"{file_path} invalid YAML — skipped"

    if not isinstance(parsed, dict) or "scenarios" not in parsed:
        return None, "not index format — skipped"

    entries = parsed.get("scenarios") or []
    if not isinstance(entries, list) or len(entries) == 0:
        return None, "no entries — skipped"

    missing = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ref_file = entry.get("file", "")
        if not ref_file:
            missing.append(f"{entry.get('id', '?')}: no 'file' key")
            continue

        if ref_file.startswith("frameworks/"):
            # Local-first: handles zeroth PRs where files exist on the branch
            # but not yet on remote main.
            if (repo / ref_file).exists():
                continue
            # Remote fallback: handles instance repos referencing zeroth canonical.
            url = f"https://raw.githubusercontent.com/Malstrom/zeroth/{zeroth_ref}/{ref_file}"
            if not _fetch_url(url):
                missing.append(ref_file)
        else:
            if not (repo / ref_file).exists():
                missing.append(ref_file)

    if missing:
        for m in missing:
            print(f"    missing: {m}")
        return False, f"{len(missing)}/{len(entries)} file(s) missing"

    return True, f"{len(entries)} file(s) found"


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
    parsed = _parse_yaml(repo, ".agent.yml")
    fa = parsed.get("file_access", {}) or {}
    pattern = check["pattern"]
    mode = check["mode"].lower()
    all_modes = {k: v for k, v in fa.items() if isinstance(v, list)}
    if all_modes:
        in_correct = pattern in (all_modes.get(mode) or [])
        in_write = pattern in (all_modes.get("write") or [])
        if not in_correct:
            print(f"    '{pattern}' not found in file_access.{mode}")
        if in_write:
            print(f"    '{pattern}' is also in file_access.write — must not be writable")
        return in_correct and not in_write, ""
    val = str(fa.get(pattern, "")).lower()
    return mode in val, ""


def proxy_write_ahead_rule(repo: Path, check: dict) -> tuple:
    content = _read_file(repo, ".agent.yml")
    return check["contains"] in content, ""


# ---------------------------------------------------------------------------
# Cross-ref check proxy
# ---------------------------------------------------------------------------

def _resolve_dotted(data: dict, dotted_key: str):
    """Walk a dict by dotted key path. Returns the value or None."""
    parts = dotted_key.split(".")
    val = data
    for p in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
    return val


def proxy_cross_ref_check(repo: Path, check: dict) -> tuple:
    """
    Execute a single cross_refs entry from structure.yml.

    check keys (mirrors structure.yml cross_refs entry):
      label             — already used by run_check as the report label
      source            — 'last_session.{field}' OR a dir path like 'kiroku/nikki/'
      source_group      — (int) which filename_regex group to extract (1-based)
      source_regex      — regex string with capture groups
      source_filter     — {group: int, value: str} to restrict to specific type
      gakusei_state_file— filename of the state file (e.g. '.gakusei.yml')
      target            — 'topics', 'goals' (state file key), or 'kata/{value}.md'
      target_type       — 'keys' | 'file_exists' | 'file_glob'
      target_glob_pattern — required when target_type is 'file_glob'
      level             — 'error' | 'warning'
    """
    state_file = check.get("gakusei_state_file", ".gakusei.yml")
    gakusei = _parse_yaml(repo, state_file)
    source = check["source"]
    target = check["target"]
    target_type = check["target_type"]
    level = check.get("level", "error")
    is_warning = level == "warning"

    # --- Resolve the set of values to check ---
    values: set[str] = set()

    if source.startswith("last_session."):
        # Value comes from state file scalar field
        field = source[len("last_session."):]
        ls = gakusei.get("last_session") or {}
        val = ls.get(field) if isinstance(ls, dict) else None
        if val:
            values = {str(val)}
        else:
            return None, f"{state_file} last_session.{field} is empty — skipped"

    else:
        # Value comes from filenames in a directory
        source_dir = repo / source.rstrip("/")
        if not source_dir.is_dir():
            return None, f"{source} not found — skipped"

        source_regex = check.get("source_regex", "")
        source_group = check.get("source_group", 1)
        source_filter = check.get("source_filter")
        pattern = re.compile(source_regex) if source_regex else None

        for f in source_dir.iterdir():
            if f.suffix != ".yml" or f.name in {".keep", ".gitkeep"}:
                continue
            if pattern:
                m = pattern.match(f.name)
                if not m:
                    continue
                # Apply type filter if present
                if source_filter:
                    filter_group = source_filter.get("group", 2)
                    filter_value = source_filter.get("value", "")
                    try:
                        if m.group(filter_group) != filter_value:
                            continue
                    except IndexError:
                        continue
                try:
                    values.add(m.group(source_group))
                except IndexError:
                    continue
            else:
                values.add(f.stem)

        if not values:
            return None, f"no valid files found in {source} — skipped"

    # --- Resolve the target and check each value ---
    violations: list[str] = []

    for value in sorted(values):
        if target_type == "keys":
            # value must be a key in state_file[target]
            target_dict = _resolve_dotted(gakusei, target)
            if not isinstance(target_dict, dict):
                return None, f"{state_file}.{target} is not a dict or missing — skipped"
            if value not in target_dict:
                violations.append(value)

        elif target_type == "file_exists":
            # target path may contain {value} placeholder
            resolved_path = target.replace("{value}", value)
            if not (repo / resolved_path).exists():
                violations.append(resolved_path)

        elif target_type == "file_glob":
            # target_glob_pattern with {value} placeholder, matched in target dir
            target_dir_path = repo / target.rstrip("/")
            glob_pattern = check.get("target_glob_pattern", "").replace("{value}", value)
            if not glob_pattern:
                return ERROR, "target_glob_pattern missing in cross_ref entry"
            if not target_dir_path.is_dir():
                violations.append(f"{target}{glob_pattern}")
                continue
            matches = list(target_dir_path.glob(glob_pattern))
            if not matches:
                violations.append(f"{target}{glob_pattern}")

        else:
            return ERROR, f"unknown target_type '{target_type}'"

    if violations:
        detail = "missing <- " + ", ".join(violations)
        # Warnings become None (skip/warn), errors become False (fail)
        return (None if is_warning else False), detail

    return True, f"{len(values)} value(s) checked"


# ---------------------------------------------------------------------------
# Proxy registry
# ---------------------------------------------------------------------------

PROXY_REGISTRY = {
    "file_exists": proxy_file_exists,
    "dir_has_subfolders": proxy_dir_has_subfolders,
    "dir_has_templates": proxy_dir_has_templates,
    "template_matches_zeroth": proxy_template_matches_zeroth,
    "template_keys_match_framework": proxy_template_keys_match_framework,
    "generated_files_match_template": proxy_generated_files_match_template,
    "yaml_key_exists": proxy_yaml_key_exists,
    "yaml_key_absent": proxy_yaml_key_absent,
    "yaml_key_equals": proxy_yaml_key_equals,
    "yaml_key_contains": proxy_yaml_key_contains,
    "yaml_first_key": proxy_yaml_first_key,
    "yaml_levels_valid": proxy_yaml_levels_valid,
    "yaml_subkeys_exist": proxy_yaml_subkeys_exist,
    "scenario_present": proxy_scenario_present,
    "scenario_last": proxy_scenario_last,
    "scenario_not_present": proxy_scenario_not_present,
    "scenario_input_sources": proxy_scenario_input_sources,
    "scenario_no_forbidden_modules": proxy_scenario_no_forbidden_modules,
    "scenarios_index_valid": proxy_scenarios_index_valid,
    "scenarios_index_files_exist": proxy_scenarios_index_files_exist,
    "handler_present": proxy_handler_present,
    "handler_has_key": proxy_handler_has_key,
    "text_search": proxy_text_search,
    "token_count": proxy_token_count,
    "file_access_mode": proxy_file_access_mode,
    "write_ahead_rule": proxy_write_ahead_rule,
    "cross_ref_check": proxy_cross_ref_check,
}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _section_framework(section_name: str) -> str:
    if section_name == "zeroth — agent":
        return "_zeroth_agent"
    if "@" in section_name:
        return section_name.split("@")[0].strip()
    if " — " in section_name:
        return section_name.split(" — ")[0].strip()
    return section_name


def _framework_display(fw_key: str) -> str:
    if fw_key == "_zeroth_agent":
        return "zeroth — agent"
    return fw_key


class Report:
    def __init__(self, repo: Path):
        self.repo = repo
        self.entries = []
        self.current_section = None
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errored = 0
        self.failures = []
        self.ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def add(self, label: str, result, note: str = "", file: str = "", rule: str = ""):
        if result is True:
            self.passed += 1
            icon = "\u2705"
            kind = "passed"
        elif result is ERROR:
            self.errored += 1
            icon = "\U0001f4a5"
            kind = "errored"
            msg = f"Giskard error: {label}"
            if note:
                msg += f" — {note}"
            _gh_annotation("error", msg, file)
        elif result is False:
            self.failed += 1
            icon = "\u274c"
            kind = "failed"
            self.failures.append({"label": label, "file": file, "rule": rule})
            msg = f"Giskard FAILED: {label}"
            if note:
                msg += f" — {note}"
            if rule:
                msg += f" (rule: {rule})"
            _gh_annotation("error", msg, file)
        else:
            self.skipped += 1
            icon = "\u26a0\ufe0f"
            kind = "skipped"
        suffix = f" — {note}" if note else ""
        line = f"  {icon} {label}{suffix}"
        print(line)
        self.entries.append({
            "section": self.current_section or "checks",
            "kind": kind,
            "line": line,
        })

    def section(self, name: str):
        self.current_section = name
        print(f"\n\u2502 {name}")

    def save(self) -> Path:
        out = self.repo / "giskard-report.md"
        if self.errored > 0:
            status = "\U0001f4a5 error"
        elif self.failed > 0:
            status = "\u274c failed"
        else:
            status = "\u2705 passed"
        header = [
            "# \U0001f916 Giskard report",
            "",
            f"- **repo**: {self.repo.name}",
            f"- **date**: {self.ts}",
            f"- **result**: {status} — {self.passed} passed / {self.failed} failed / {self.skipped} skipped / {self.errored} errored",
            "",
        ]

        by_section: dict[str, list] = {}
        for e in self.entries:
            by_section.setdefault(e["section"], []).append(e)

        by_framework: dict[str, list[str]] = {}
        for section_name in by_section:
            fw = _section_framework(section_name)
            by_framework.setdefault(fw, []).append(section_name)

        fw_order = sorted(
            by_framework.keys(),
            key=lambda k: (0 if k == "_zeroth_agent" else 1, k),
        )

        body = []
        for fw_key in fw_order:
            fw_sections = by_framework[fw_key]
            all_items = []
            for sec in fw_sections:
                all_items.extend(by_section[sec])

            fw_passed = sum(1 for i in all_items if i["kind"] == "passed")
            fw_failed = sum(1 for i in all_items if i["kind"] == "failed")
            fw_skipped = sum(1 for i in all_items if i["kind"] == "skipped")
            fw_errored = sum(1 for i in all_items if i["kind"] == "errored")

            if fw_failed == 0 and fw_errored == 0 and fw_skipped == 0:
                fw_status = f"\u2705 {fw_passed}/{len(all_items)}"
            elif fw_failed or fw_errored:
                fw_status = f"\u274c {fw_passed} passed / {fw_failed} failed / {fw_skipped} skipped / {fw_errored} errored"
            else:
                fw_status = f"\u26a0\ufe0f {fw_passed} passed / {fw_failed} failed / {fw_skipped} skipped / {fw_errored} errored"

            body.append(f"### {_framework_display(fw_key)} {fw_status}")
            body.append("")

            for sec in fw_sections:
                items = by_section[sec]
                n_passed = sum(1 for i in items if i["kind"] == "passed")
                n_failed = sum(1 for i in items if i["kind"] == "failed")
                n_skipped = sum(1 for i in items if i["kind"] == "skipped")
                n_errored = sum(1 for i in items if i["kind"] == "errored")

                if len(fw_sections) > 1:
                    check_type = sec.split(" — ")[-1] if " — " in sec else sec
                    if n_failed == 0 and n_errored == 0 and n_skipped == 0:
                        body.append(f"**{check_type}** \u2705 {n_passed}/{len(items)}")
                    else:
                        sec_status = "\u274c" if (n_failed or n_errored) else "\u26a0\ufe0f"
                        body.append(f"**{check_type}** {sec_status}")
                    body.append("")

                for item in items:
                    if item["kind"] != "passed":
                        body.append(item["line"])
                if n_passed > 0 and (n_failed > 0 or n_skipped > 0 or n_errored > 0):
                    body.append(f"  \u2139\ufe0f {n_passed} passed checks hidden")

            body.append("")

        with open(out, "w") as f:
            f.write("\n".join(header + body).rstrip() + "\n")
        print(f"\n[Giskard] report written to {out}")
        return out

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.errored == 0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

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
        report.add(
            label, result, note,
            file=check.get("file", check.get("target", "")),
            rule=check.get("rule", ""),
        )
    except Exception as e:
        tb = traceback.format_exc().strip().splitlines()[-1]
        report.add(label, ERROR, f"{tb}")
