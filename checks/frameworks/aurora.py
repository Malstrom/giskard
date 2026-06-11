"""
checks/frameworks/aurora.py — aurora framework-specific checks (layer 2)

Runs after universal rules (layer 1). Validates aurora-specific structure:
- Required files and directories
- .aurora.yml structure
- templates/ completeness
- handler reindex_check
- referential integrity: inbox → contacts, clients, log (aggregated)
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
]

STRUCTURE_CHECKS = [
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
    {
        "label": "templates/ has all required aurora templates",
        "proxy": "dir_has_templates",
        "target": "templates",
        "required_files": REQUIRED_TEMPLATES,
        "rule": "aurora/structure.yml",
    },
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
    {
        "label": "handler reindex_check present",
        "proxy": "handler_present",
        "handler": "reindex_check",
        "file": ".agent.yml",
        "rule": "aurora/structure.yml",
    },
]


def _read_inbox_file(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _check_referential_integrity(repo: Path, report: Report) -> None:
    """
    Aggregated referential integrity check.
    Iterates all clients/*/inbox/*.yml, collects anomalies,
    then emits one result per category.

    Categories:
    - client dirs missing   → ERROR
    - contacts missing      → WARNING
    - assigned_to missing   → WARNING
    - log dirs missing      → WARNING
    """
    clients_dir = repo / "clients"
    if not clients_dir.is_dir():
        return

    # slug → [rel_path, ...]
    missing_client_dirs: dict = defaultdict(list)
    # contact → [rel_path, ...]
    missing_contacts: dict = defaultdict(list)
    # contact → [rel_path, ...]
    missing_assigned: dict = defaultdict(list)
    # slug → [rel_path, ...]
    missing_logs: dict = defaultdict(list)

    total_files = 0

    for client_dir in sorted(clients_dir.iterdir()):
        if not client_dir.is_dir():
            continue
        inbox_dir = client_dir / "inbox"
        if not inbox_dir.is_dir():
            continue
        inbox_files = [f for f in inbox_dir.iterdir() if f.suffix == ".yml"]
        if not inbox_files:
            continue

        for inbox_file in sorted(inbox_files):
            data = _read_inbox_file(inbox_file)
            rel = str(inbox_file.relative_to(repo))
            total_files += 1

            slug = data.get("client") or client_dir.name

            # 1 — client dir
            if not (repo / "clients" / slug).is_dir():
                missing_client_dirs[slug].append(rel)

            # 2 — contact
            contact = data.get("contact")
            if contact and not (repo / "contacts" / f"{contact}.yml").exists():
                missing_contacts[contact].append(rel)

            # 3 — assigned_to
            assigned_to = data.get("assigned_to")
            if assigned_to and assigned_to != "null":
                if not (repo / "contacts" / f"{assigned_to}.yml").exists():
                    missing_assigned[assigned_to].append(rel)

            # 4 — log dir when status != open
            status = data.get("status", "open")
            if status and status != "open":
                if not (repo / "log" / slug).is_dir():
                    missing_logs[slug].append(rel)

    if total_files == 0:
        report.add("referential integrity", None, "no inbox files found — skipped")
        return

    # --- emit aggregated results ---

    # client dirs
    if missing_client_dirs:
        for slug, files in sorted(missing_client_dirs.items()):
            detail = f"clients/{slug}/ missing ← " + ", ".join(files)
            report.add(f"client dir missing: {slug}", False, detail, rule="aurora/structure.yml")
            _gh_annotation("error", f"giskard ERROR: client dir 'clients/{slug}/' missing", files[0])
    else:
        report.add(f"all client dirs aligned ({total_files} files)", True)

    # contacts
    if missing_contacts:
        for contact, files in sorted(missing_contacts.items()):
            detail = f"contacts/{contact}.yml missing ← " + ", ".join(files)
            report.add(f"contact missing: {contact}", None, detail, rule="aurora/structure.yml")
            _gh_annotation("warning", f"giskard WARNING: contacts/{contact}.yml missing", files[0])
    else:
        report.add(f"all contacts resolved ({total_files} files)", True)

    # assigned_to
    if missing_assigned:
        for contact, files in sorted(missing_assigned.items()):
            detail = f"contacts/{contact}.yml missing (assigned_to) ← " + ", ".join(files)
            report.add(f"assigned_to missing: {contact}", None, detail, rule="aurora/structure.yml")
            _gh_annotation("warning", f"giskard WARNING: contacts/{contact}.yml missing (assigned_to)", files[0])
    else:
        report.add(f"all assigned_to resolved ({total_files} files)", True)

    # log dirs
    if missing_logs:
        for slug, files in sorted(missing_logs.items()):
            detail = f"log/{slug}/ missing ← " + ", ".join(files)
            report.add(f"log dir missing for worked client: {slug}", None, detail, rule="aurora/structure.yml")
            _gh_annotation("warning", f"giskard WARNING: log/{slug}/ missing", files[0])
    else:
        report.add(f"all log dirs present for worked clients ({total_files} files)", True)


def run(repo: Path, report: Report) -> None:
    report.section("aurora")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)

    report.section("aurora — referential integrity")
    _check_referential_integrity(repo, report)
