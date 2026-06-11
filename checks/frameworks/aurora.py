"""
checks/frameworks/aurora.py — aurora framework-specific checks (layer 2)

Runs after universal rules (layer 1). Validates aurora-specific structure:
- Required files and directories
- .aurora.yml structure
- templates/ completeness
- handler reindex_check
- session_start reads .aurora.yml
- referential integrity: inbox → contacts, clients, log
"""

import yaml
from pathlib import Path
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
    For every inbox file in clients/*/inbox/:
    - data['client'] dir exists in clients/     → ERROR if missing
    - contact file exists in contacts/           → WARNING if missing
    - assigned_to contact exists in contacts/    → WARNING if missing
    - if status != open → log/{client}/ exists  → WARNING if missing

    Skipped entirely if no inbox files exist anywhere.
    """
    clients_dir = repo / "clients"
    if not clients_dir.is_dir():
        return

    found_any_inbox = False

    for client_dir in sorted(clients_dir.iterdir()):
        if not client_dir.is_dir():
            continue
        inbox_dir = client_dir / "inbox"
        if not inbox_dir.is_dir():
            continue
        inbox_files = [f for f in inbox_dir.iterdir() if f.suffix == ".yml"]
        if not inbox_files:
            continue

        found_any_inbox = True

        for inbox_file in sorted(inbox_files):
            data = _read_inbox_file(inbox_file)
            rel = str(inbox_file.relative_to(repo))

            # slug from yaml field, not from dir name
            slug = data.get("client") or client_dir.name

            # 1 — client dir declared in yaml exists
            client_path = repo / "clients" / slug
            if not client_path.is_dir():
                msg = f"client dir 'clients/{slug}/' missing (declared in {rel})"
                report.add(f"client dir exists: {slug}", False, msg, file=rel, rule="aurora/structure.yml")
            else:
                report.add(f"client dir exists: {slug}", True, file=rel)

            # 2 — contact field exists in contacts/
            contact = data.get("contact")
            if contact:
                contact_path = repo / "contacts" / f"{contact}.yml"
                if not contact_path.exists():
                    msg = f"contacts/{contact}.yml missing (referenced in {rel})"
                    report.add(f"contact exists: {contact}", None, msg, file=rel, rule="aurora/structure.yml")
                    _gh_annotation("warning", f"giskard WARNING: {msg}", rel)
                else:
                    report.add(f"contact exists: {contact}", True, file=rel)

            # 3 — assigned_to contact exists in contacts/
            assigned_to = data.get("assigned_to")
            if assigned_to and assigned_to != "null":
                assigned_path = repo / "contacts" / f"{assigned_to}.yml"
                if not assigned_path.exists():
                    msg = f"contacts/{assigned_to}.yml missing (assigned_to in {rel})"
                    report.add(f"assigned_to exists: {assigned_to}", None, msg, file=rel, rule="aurora/structure.yml")
                    _gh_annotation("warning", f"giskard WARNING: {msg}", rel)
                else:
                    report.add(f"assigned_to exists: {assigned_to}", True, file=rel)

            # 4 — if status != open, log/{slug}/ must exist
            status = data.get("status", "open")
            if status and status != "open":
                log_dir = repo / "log" / slug
                if not log_dir.is_dir():
                    msg = f"log/{slug}/ missing but status='{status}' in {rel}"
                    report.add(f"log dir exists for worked client: {slug}", None, msg, file=rel, rule="aurora/structure.yml")
                    _gh_annotation("warning", f"giskard WARNING: {msg}", rel)
                else:
                    report.add(f"log dir exists for worked client: {slug}", True, file=rel)

    if not found_any_inbox:
        report.add("referential integrity", None, "no inbox files found — skipped")


def run(repo: Path, report: Report) -> None:
    report.section("aurora")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)

    report.section("aurora — referential integrity")
    _check_referential_integrity(repo, report)
