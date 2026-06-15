"""
checks/frameworks/dojo.py — dojo framework checks (instance mode)

All validation rules are inferred at runtime from:
  zeroth/frameworks/dojo/structure.yml

Zero dojo-specific values are hardcoded here. To change what giskard
checks, update zeroth — not this file.

This module only contains:
  - run()           — orchestration shell
  - _check_filename_patterns()  — nikki/makimono filename validation
    (kept as code because it needs per-file gh annotations; not expressible
     as a single cross_ref entry)

Section order:
  dojo — structure   (required files + dirs, from structure.yml)
  dojo — files       (key presence per template, from structure.yml)
  dojo — refs        (cross-references, from structure.yml cross_refs)
"""

import re
from pathlib import Path

from core import run_check, Report, _gh_annotation, fetch_zeroth_structure

_IGNORED_NAMES = {".keep", ".gitkeep"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_structure_checks(spec: dict) -> list[dict]:
    """Generate file_exists checks from structure.yml structure block."""
    checks = []
    for path_key, meta in (spec.get("structure") or {}).items():
        target = path_key.rstrip("/")
        checks.append({
            "label": f"{path_key} not found",
            "proxy": "file_exists",
            "target": target,
            "file": path_key,
            "rule": "dojo/structure.yml",
        })
    return checks


def _build_gakusei_key_checks(spec: dict) -> list[dict]:
    """Generate yaml_key_exists checks from gakusei_state_file required_keys."""
    state_file = spec.get("gakusei_state_file", ".gakusei.yml")
    required_keys = (
        (spec.get("structure") or {})
        .get(state_file, {})
        .get("required_keys") or []
    )
    return [
        {
            "label": f"{state_file} missing '{key}' field",
            "proxy": "yaml_key_exists",
            "file": state_file,
            "key": key,
            "rule": "dojo/structure.yml",
        }
        for key in required_keys
    ]


def _build_file_key_checks(repo: Path, spec: dict) -> list[dict]:
    """Generate generated_files_match_template checks from structure.yml.

    For each dir entry with filename_pattern + template:
    - pass template_src unchanged (_resolve_template_content handles zeroth paths)
    - skip silently if the dir has no matching files AND access == 'write-once'
      (empty write-once dirs are normal at repo creation time)
    """
    checks = []
    for path_key, meta in (spec.get("structure") or {}).items():
        if not path_key.endswith("/"):
            continue
        pattern = (meta or {}).get("filename_pattern")
        template_src = (meta or {}).get("template", "")
        if not pattern or not template_src:
            continue

        # Skip check entirely for write-once dirs that are still empty
        if (meta or {}).get("access") == "write-once":
            dir_path = repo / path_key.rstrip("/")
            if dir_path.is_dir():
                yml_files = [f for f in dir_path.iterdir()
                             if f.suffix == ".yml" and f.name not in _IGNORED_NAMES]
                if not yml_files:
                    continue

        glob_pattern = re.sub(r"\{[^}]+\}", "*", pattern)
        glob_pattern = glob_pattern.replace("YYYY", "????").replace("MM", "??").replace("DD", "??")
        dir_glob = path_key.rstrip("/") + "/" + glob_pattern

        checks.append({
            "label": f"{path_key} files: keys missing vs template",
            "proxy": "generated_files_match_template",
            "glob": dir_glob,
            "template": template_src,
            "rule": "dojo/files.yml",
        })
    return checks


def _build_cross_ref_checks(repo: Path, spec: dict) -> list[dict]:
    """Convert structure.yml cross_refs entries into run_check dicts.

    Cross_refs whose source is a write-once dir that is still empty
    are silently dropped — nothing to cross-reference yet.
    """
    state_file = spec.get("gakusei_state_file", ".gakusei.yml")
    structure = spec.get("structure") or {}
    checks = []
    for entry in (spec.get("cross_refs") or []):
        source = entry.get("source", "")

        # Drop cross_refs whose source is a write-once dir with no files yet
        if source.endswith("/"):
            meta = structure.get(source, {})
            if (meta or {}).get("access") == "write-once":
                dir_path = repo / source.rstrip("/")
                if dir_path.is_dir():
                    yml_files = [f for f in dir_path.iterdir()
                                 if f.suffix == ".yml" and f.name not in _IGNORED_NAMES]
                    if not yml_files:
                        continue

        check = dict(entry)
        check["proxy"] = "cross_ref_check"
        check["gakusei_state_file"] = state_file
        check["rule"] = "dojo/structure.yml"
        if source.endswith("/"):
            meta = structure.get(source, {})
            if meta and meta.get("filename_regex"):
                check.setdefault("source_regex", meta["filename_regex"])
        checks.append(check)
    return checks


# ---------------------------------------------------------------------------
# Filename pattern validation
# ---------------------------------------------------------------------------

def _check_filename_patterns(repo: Path, report: Report, spec: dict) -> None:
    """Validate nikki and makimono filenames against structure.yml patterns."""
    structure = spec.get("structure") or {}

    for dir_key, meta in structure.items():
        if not dir_key.endswith("/"):
            continue
        regex_str = (meta or {}).get("filename_regex")
        type_values = (meta or {}).get("type_values")
        if not regex_str:
            continue

        dir_path = repo / dir_key.rstrip("/")
        if not dir_path.is_dir():
            continue

        pattern = re.compile(regex_str)
        groups = (meta or {}).get("filename_groups") or {}
        type_group = next((int(k) for k, v in groups.items() if v == "type"), None)

        bad_names, bad_types, good = [], [], []
        for f in dir_path.iterdir():
            if f.name in _IGNORED_NAMES or f.suffix != ".yml":
                continue
            m = pattern.match(f.name)
            if not m:
                bad_names.append(str(f.relative_to(repo)))
            elif type_group and type_values:
                try:
                    t = m.group(type_group)
                except IndexError:
                    t = ""
                if t not in type_values:
                    bad_types.append(f"{f.name} (type='{t}')")
                else:
                    good.append(f.name)
            else:
                good.append(f.name)

        if not good and not bad_names and not bad_types:
            # empty dir — nothing to validate
            continue

        if bad_names:
            detail = "invalid filename pattern <- " + ", ".join(sorted(bad_names))
            report.add(f"{dir_key} filenames: pattern not respected", False, detail, rule="dojo/structure.yml")
            _gh_annotation("error", f"giskard ERROR: {dir_key} invalid filename", bad_names[0])
        elif bad_types:
            allowed = "|".join(type_values)
            detail = f"invalid type (must be {allowed}) <- " + ", ".join(sorted(bad_types))
            report.add(f"{dir_key} filenames: invalid type value", False, detail, rule="dojo/structure.yml")
        else:
            report.add(f"all {dir_key} filenames match pattern ({len(good)} files)", True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(repo: Path, report: Report) -> None:
    spec = fetch_zeroth_structure("dojo")
    if not spec:
        report.add(
            "could not fetch zeroth/frameworks/dojo/structure.yml — all dojo checks skipped",
            None, "check network access to raw.githubusercontent.com"
        )
        return

    state_file = spec.get("gakusei_state_file", ".gakusei.yml")

    # --- Structure: required files and dirs ---
    report.section("dojo — structure")
    for check in _build_structure_checks(spec):
        run_check(repo, check, report)

    gakusei_path = repo / state_file
    if not gakusei_path.exists():
        report.add(
            f"{state_file} absent — onboarding not yet run", None,
            "run the dojo onboarding scenario to generate this file",
            rule="dojo/structure.yml", file=state_file
        )
    else:
        for check in _build_gakusei_key_checks(spec):
            run_check(repo, check, report)

    # --- Files: template key coverage ---
    report.section("dojo — files")
    for check in _build_file_key_checks(repo, spec):
        run_check(repo, check, report)

    # --- Refs: cross-file consistency ---
    report.section("dojo — refs")
    _check_filename_patterns(repo, report, spec)
    for check in _build_cross_ref_checks(repo, spec):
        run_check(repo, check, report)
