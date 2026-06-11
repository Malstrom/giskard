"""
checks/frameworks/aurora.py — aurora framework checks

================================================================================
AURORA FRAMEWORK SPEC
Inferred from: aurora/.scenarios.yml + repo structure
Last updated: 2026-06-11
================================================================================

Section order (top-down, most general to most specific):

  aurora — structure
    .aurora.yml fields, required dirs, templates present,
    framework-specific handler (reindex_check)

  aurora — files
    Every generated file contains all root keys of its local template.
    Mapping (glob → template):
      clients/*/inbox/*.yml      → templates/inbox.yml
      contacts/*.yml             → templates/contact.yml
      log/*/*.yml                → templates/log.yml
      log/_index/*.yml           → templates/log_index.yml
      clients/*/playbooks/*.yml  → templates/playbook.yml
      log/*/*_*.yml              → templates/playbook_log.yml
    Skipped if no generated files exist. No network calls.

  aurora — refs
    Every reference in every file resolves to something that exists.
    Sources:
      clients/*/inbox/*.yml → client dir, contact, assigned_to, log dir
      clients/*/playbooks/*.yml → extends target, client field vs dir name

================================================================================
LABEL CONVENTION
================================================================================

Labels describe what is WRONG when the check fails.
The ❌ icon signals failure — the label completes the sentence.
  BAD:  'handler reindex_check present'   (reads as passing even when failing)
  GOOD: 'handler reindex_check not found' (clear regardless of icon)

================================================================================
KNOWN GAPS / FUTURE CHECKS
================================================================================

- output/ file naming convention not yet validated
- contacts/{slug}.yml internal field structure not yet validated
- clients/{slug}/context.yml existence not yet validated

================================================================================
"""

import yaml
from pathlib import Path
from collections import defaultdict
from core import run_check, Report, ERROR, _gh_annotation

REQUIRED_TEMPLATES = [
    "inbox.yml",
    "log.yml",
    "log_index.yml",
    "contact.yml",
    "client_context.yml",
    "playbook.yml",
    "playbook_log.yml",
    "output_csv.md",
    "output_email.md",
    "output_report.md",
]

STRUCTURE_CHECKS = [
    {
        "label": ".aurora.yml not found",
        "proxy": "file_exists",
        "target": ".aurora.yml",
        "file": ".aurora.yml",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "clients/ directory not found",
        "proxy": "file_exists",
        "target": "clients",
        "file": "clients/",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "contacts/ directory not found",
        "proxy": "file_exists",
        "target": "contacts",
        "file": "contacts/",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "log/ directory not found",
        "proxy": "file_exists",
        "target": "log",
        "file": "log/",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "playbooks/ directory not found",
        "proxy": "file_exists",
        "target": "playbooks",
        "file": "playbooks/",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "templates/ missing required aurora files",
        "proxy": "dir_has_templates",
        "target": "templates",
        "required_files": REQUIRED_TEMPLATES,
        "rule": "aurora/structure.yml",
    },
    {
        "label": ".aurora.yml missing 'version' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "version",
        "rule": "aurora/structure.yml",
    },
    {
        "label": ".aurora.yml missing 'owner' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "owner",
        "rule": "aurora/structure.yml",
    },
    {
        "label": ".aurora.yml missing 'language' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "language",
        "rule": "aurora/structure.yml",
    },
    {
        "label": ".aurora.yml missing 'clients' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "clients",
        "rule": "aurora/structure.yml",
    },
    {
        "label": ".aurora.yml missing 'work_types' field",
        "proxy": "yaml_key_exists",
        "file": ".aurora.yml",
        "key": "work_types",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "handler reindex_check not found",
        "proxy": "handler_present",
        "handler": "reindex_check",
        "file": ".agent.yml",
        "rule": "aurora/structure.yml",
    },
]

FILE_KEY_CHECKS = [
    {
        "label": "inbox files: keys missing vs templates/inbox.yml",
        "proxy": "generated_files_match_template",
        "glob": "clients/*/inbox/*.yml",
        "template": "templates/inbox.yml",
        "rule": "aurora/files.yml",
    },
    {
        "label": "contact files: keys missing vs templates/contact.yml",
        "proxy": "generated_files_match_template",
        "glob": "contacts/*.yml",
        "template": "templates/contact.yml",
        "rule": "aurora/files.yml",
    },
    {
        "label": "log session files: keys missing vs templates/log.yml",
        "proxy": "generated_files_match_template",
        "glob": "log/*/*.yml",
        "template": "templates/log.yml",
        "rule": "aurora/files.yml",
    },
    {
        "label": "log index files: keys missing vs templates/log_index.yml",
        "proxy": "generated_files_match_template",
        "glob": "log/_index/*.yml",
        "template": "templates/log_index.yml",
        "rule": "aurora/files.yml",
    },
    {
        "label": "client playbook files: keys missing vs templates/playbook.yml",
        "proxy": "generated_files_match_template",
        "glob": "clients/*/playbooks/*.yml",
        "template": "templates/playbook.yml",
        "rule": "aurora/files.yml",
    },
    {
        "label": "playbook log files: keys missing vs templates/playbook_log.yml",
        "proxy": "generated_files_match_template",
        "glob": "log/*/*_*.yml",
        "template": "templates/playbook_log.yml",
        "rule": "aurora/files.yml",
    },
]


def _read_yaml_file(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _check_refs(repo: Path, report: Report) -> None:
    """
    Aggregated referential integrity check.

    Sources:
      clients/*/inbox/*.yml
        - client: {slug}       → clients/{slug}/ must exist          ERROR
        - contact: {slug}      → contacts/{slug}.yml must exist       WARNING
        - assigned_to: {slug}  → contacts/{slug}.yml must exist       WARNING
        - status != open       → log/{slug}/ must exist               WARNING

      clients/*/playbooks/*.yml
        - extends: {name}      → playbooks/{name}.yml must exist      ERROR
        - client: {declared}   → must match containing dir name       WARNING
    """
    clients_dir = repo / "clients"
    if not clients_dir.is_dir():
        return

    missing_client_dirs: dict = defaultdict(list)
    missing_contacts: dict = defaultdict(list)
    missing_assigned: dict = defaultdict(list)
    missing_logs: dict = defaultdict(list)
    missing_extends: dict = defaultdict(list)
    client_mismatch: list = []

    inbox_total = 0
    playbook_total = 0

    for client_dir in sorted(clients_dir.iterdir()):
        if not client_dir.is_dir():
            continue

        # inbox refs
        inbox_dir = client_dir / "inbox"
        if inbox_dir.is_dir():
            for inbox_file in sorted(f for f in inbox_dir.iterdir() if f.suffix == ".yml"):
                data = _read_yaml_file(inbox_file)
                rel = str(inbox_file.relative_to(repo))
                inbox_total += 1

                slug = data.get("client") or client_dir.name
                if not (repo / "clients" / slug).is_dir():
                    missing_client_dirs[slug].append(rel)

                contact = data.get("contact")
                if contact and not (repo / "contacts" / f"{contact}.yml").exists():
                    missing_contacts[contact].append(rel)

                assigned_to = data.get("assigned_to")
                if assigned_to and assigned_to != "null":
                    if not (repo / "contacts" / f"{assigned_to}.yml").exists():
                        missing_assigned[assigned_to].append(rel)

                status = data.get("status", "open")
                if status and status != "open":
                    if not (repo / "log" / slug).is_dir():
                        missing_logs[slug].append(rel)

        # playbook refs
        pb_dir = client_dir / "playbooks"
        if pb_dir.is_dir():
            for pb_file in sorted(f for f in pb_dir.iterdir() if f.suffix == ".yml"):
                data = _read_yaml_file(pb_file)
                rel = str(pb_file.relative_to(repo))
                playbook_total += 1

                extends = data.get("extends")
                if extends and not (repo / "playbooks" / f"{extends}.yml").exists():
                    missing_extends[extends].append(rel)

                declared_client = data.get("client")
                if declared_client and declared_client != client_dir.name:
                    client_mismatch.append((declared_client, client_dir.name, rel))

    total = inbox_total + playbook_total
    if total == 0:
        report.add("no files to check refs on", None, "skipped")
        return

    # inbox refs results
    if missing_client_dirs:
        for slug, files in sorted(missing_client_dirs.items()):
            detail = f"clients/{slug}/ missing ← " + ", ".join(files)
            report.add(f"client dir missing: {slug}", False, detail, rule="aurora/refs.yml")
            _gh_annotation("error", f"giskard ERROR: clients/{slug}/ missing", files[0])
    else:
        report.add(f"all client dirs resolved ({inbox_total} inbox files)", True)

    if missing_contacts:
        for contact, files in sorted(missing_contacts.items()):
            detail = f"contacts/{contact}.yml missing ← " + ", ".join(files)
            report.add(f"contact not found: {contact}", None, detail, rule="aurora/refs.yml")
            _gh_annotation("warning", f"giskard WARNING: contacts/{contact}.yml missing", files[0])
    else:
        report.add(f"all contacts resolved ({inbox_total} inbox files)", True)

    if missing_assigned:
        for contact, files in sorted(missing_assigned.items()):
            detail = f"contacts/{contact}.yml missing (assigned_to) ← " + ", ".join(files)
            report.add(f"assigned_to not found: {contact}", None, detail, rule="aurora/refs.yml")
            _gh_annotation("warning", f"giskard WARNING: contacts/{contact}.yml missing (assigned_to)", files[0])
    else:
        report.add(f"all assigned_to resolved ({inbox_total} inbox files)", True)

    if missing_logs:
        for slug, files in sorted(missing_logs.items()):
            detail = f"log/{slug}/ missing ← " + ", ".join(files)
            report.add(f"log dir not found for worked client: {slug}", None, detail, rule="aurora/refs.yml")
            _gh_annotation("warning", f"giskard WARNING: log/{slug}/ missing", files[0])
    else:
        report.add(f"all log dirs present for worked clients ({inbox_total} inbox files)", True)

    # playbook refs results
    if missing_extends:
        for parent, files in sorted(missing_extends.items()):
            detail = f"playbooks/{parent}.yml missing ← " + ", ".join(files)
            report.add(f"extends target not found: {parent}", False, detail, rule="aurora/refs.yml")
            _gh_annotation("error", f"giskard ERROR: playbooks/{parent}.yml missing", files[0])
    else:
        report.add(f"all extends targets resolved ({playbook_total} playbook files)", True)

    if client_mismatch:
        for declared, dir_name, rel in sorted(client_mismatch):
            msg = f"declared 'client: {declared}' but in clients/{dir_name}/"
            report.add(f"client field mismatch: {declared} vs {dir_name}", None, msg, file=rel, rule="aurora/refs.yml")
            _gh_annotation("warning", f"giskard WARNING: {msg} in {rel}", rel)
    else:
        report.add(f"all playbook client fields match dir ({playbook_total} playbook files)", True)


def run(repo: Path, report: Report) -> None:
    report.section("aurora — structure")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)

    report.section("aurora — files")
    for check in FILE_KEY_CHECKS:
        run_check(repo, check, report)

    report.section("aurora — refs")
    _check_refs(repo, report)
