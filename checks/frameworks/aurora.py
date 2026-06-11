"""
checks/frameworks/aurora.py — aurora framework checks (layer 2)

================================================================================
AURORA FRAMEWORK SPEC
Inferred from: aurora/.scenarios.yml + repo structure
Last updated: 2026-06-11
================================================================================

## What is aurora

aurora is a client-work operating system. An agent uses it to manage ongoing
work relationships with external clients: ingesting tasks, delegating work,
executing playbooks, logging sessions, and drafting communications.

Directory structure:

  .aurora.yml                         — framework config (clients list, work_types, owner)
  clients/{slug}/
    inbox/        — work assignments as yml files (one per task)
    context.yml   — client background, preferences, history summary
    summary.md    — auto-updated client overview
    playbooks/    — client-specific playbook overrides (extends general)
    output/       — produced files: report, email, csv (typed, named by date+playbook+type)
  contacts/{slug}.yml                 — contact definitions (people, not clients)
  log/{client}/                       — session logs (IMMUTABLE after creation)
    {date}.yml    — work session log
    {date}_{playbook}.yml — playbook execution log
  log/_index/{year}.yml               — aggregated annual log index
  playbooks/{name}.yml                — general playbooks (reusable, no client refs)
  templates/                          — canonical templates for all writable file types

================================================================================
CHECK GROUPS AND REASONING
================================================================================

## 1 — Structure checks (ERROR on failure)

Source scenarios: session_start (reads .aurora.yml, clients/),
                  ingest_task (reads templates/inbox.yml, writes clients/{slug}/inbox/),
                  work_session (reads playbooks/{work_type}.yml)

.aurora.yml must exist and have: version, owner, language, clients, work_types
clients/, contacts/, log/, playbooks/ must exist
templates/ must have all required files
handler reindex_check must be present in .agent.yml

## 2 — Generated file key validation (local, no network)

For every generated file type, root keys are compared against the
corresponding local template. The template is the source of truth.

Mapping:
  clients/*/inbox/*.yml      → templates/inbox.yml
  contacts/*.yml             → templates/contact.yml
  log/*/*.yml                → templates/log.yml
  log/_index/*.yml           → templates/log_index.yml
  clients/*/playbooks/*.yml  → templates/playbook.yml
  log/*/*_*.yml              → templates/playbook_log.yml

  → Missing key = agent creates files with missing fields = silent data loss.
  → Skipped if no generated files exist yet (new repo).

## 3 — Referential integrity (aggregated, mixed ERROR/WARNING)

For every clients/*/inbox/*.yml:
  client dir missing — ERROR
  contact missing — WARNING
  assigned_to missing — WARNING
  log dir missing for worked client — WARNING

## 4 — Playbook structure (ERROR/WARNING)

For every clients/*/playbooks/*.yml:
  extends missing — ERROR
  extends target missing — ERROR
  client field mismatch — WARNING

================================================================================
KNOWN GAPS / FUTURE CHECKS
================================================================================

- output/ file naming convention not yet validated
- contacts/{slug}.yml internal structure not yet validated
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

TEMPLATE_KEY_CHECKS = [
    {
        "label": "inbox files match template keys",
        "proxy": "generated_files_match_template",
        "glob": "clients/*/inbox/*.yml",
        "template": "templates/inbox.yml",
        "rule": "aurora/templates.yml",
    },
    {
        "label": "contact files match template keys",
        "proxy": "generated_files_match_template",
        "glob": "contacts/*.yml",
        "template": "templates/contact.yml",
        "rule": "aurora/templates.yml",
    },
    {
        "label": "log session files match template keys",
        "proxy": "generated_files_match_template",
        "glob": "log/*/*.yml",
        "template": "templates/log.yml",
        "rule": "aurora/templates.yml",
    },
    {
        "label": "log index files match template keys",
        "proxy": "generated_files_match_template",
        "glob": "log/_index/*.yml",
        "template": "templates/log_index.yml",
        "rule": "aurora/templates.yml",
    },
    {
        "label": "client playbook files match template keys",
        "proxy": "generated_files_match_template",
        "glob": "clients/*/playbooks/*.yml",
        "template": "templates/playbook.yml",
        "rule": "aurora/templates.yml",
    },
    {
        "label": "playbook log files match template keys",
        "proxy": "generated_files_match_template",
        "glob": "log/*/*_*.yml",
        "template": "templates/playbook_log.yml",
        "rule": "aurora/templates.yml",
    },
]


def _read_yaml_file(path: Path) -> dict:
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
    """
    clients_dir = repo / "clients"
    if not clients_dir.is_dir():
        return

    missing_client_dirs: dict = defaultdict(list)
    missing_contacts: dict = defaultdict(list)
    missing_assigned: dict = defaultdict(list)
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
            data = _read_yaml_file(inbox_file)
            rel = str(inbox_file.relative_to(repo))
            total_files += 1

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

    if total_files == 0:
        report.add("referential integrity", None, "no inbox files found — skipped")
        return

    if missing_client_dirs:
        for slug, files in sorted(missing_client_dirs.items()):
            detail = f"clients/{slug}/ missing ← " + ", ".join(files)
            report.add(f"client dir missing: {slug}", False, detail, rule="aurora/structure.yml")
            _gh_annotation("error", f"giskard ERROR: client dir 'clients/{slug}/' missing", files[0])
    else:
        report.add(f"all client dirs aligned ({total_files} files)", True)

    if missing_contacts:
        for contact, files in sorted(missing_contacts.items()):
            detail = f"contacts/{contact}.yml missing ← " + ", ".join(files)
            report.add(f"contact missing: {contact}", None, detail, rule="aurora/structure.yml")
            _gh_annotation("warning", f"giskard WARNING: contacts/{contact}.yml missing", files[0])
    else:
        report.add(f"all contacts resolved ({total_files} files)", True)

    if missing_assigned:
        for contact, files in sorted(missing_assigned.items()):
            detail = f"contacts/{contact}.yml missing (assigned_to) ← " + ", ".join(files)
            report.add(f"assigned_to missing: {contact}", None, detail, rule="aurora/structure.yml")
            _gh_annotation("warning", f"giskard WARNING: contacts/{contact}.yml missing (assigned_to)", files[0])
    else:
        report.add(f"all assigned_to resolved ({total_files} files)", True)

    if missing_logs:
        for slug, files in sorted(missing_logs.items()):
            detail = f"log/{slug}/ missing ← " + ", ".join(files)
            report.add(f"log dir missing for worked client: {slug}", None, detail, rule="aurora/structure.yml")
            _gh_annotation("warning", f"giskard WARNING: log/{slug}/ missing", files[0])
    else:
        report.add(f"all log dirs present for worked clients ({total_files} files)", True)


def _check_playbook_structure(repo: Path, report: Report) -> None:
    """
    Validates two-level playbook structure.

    For every file in clients/*/playbooks/*.yml:
    - A: 'extends' field present           → ERROR if missing
    - B: playbooks/{extends}.yml exists    → ERROR if missing
    - C: 'client' field matches dir name   → WARNING if mismatch

    Skipped if no client playbooks exist.
    """
    clients_dir = repo / "clients"
    if not clients_dir.is_dir():
        return

    missing_extends: list = []
    missing_parents: dict = defaultdict(list)
    client_mismatch: list = []
    total_files = 0

    for client_dir in sorted(clients_dir.iterdir()):
        if not client_dir.is_dir():
            continue
        pb_dir = client_dir / "playbooks"
        if not pb_dir.is_dir():
            continue
        pb_files = [f for f in pb_dir.iterdir() if f.suffix == ".yml"]
        if not pb_files:
            continue

        for pb_file in sorted(pb_files):
            data = _read_yaml_file(pb_file)
            rel = str(pb_file.relative_to(repo))
            total_files += 1

            extends = data.get("extends")
            if not extends:
                missing_extends.append(rel)
            else:
                parent_path = repo / "playbooks" / f"{extends}.yml"
                if not parent_path.exists():
                    missing_parents[extends].append(rel)

            declared_client = data.get("client")
            if declared_client and declared_client != client_dir.name:
                client_mismatch.append((declared_client, client_dir.name, rel))

    if total_files == 0:
        report.add("playbook structure", None, "no client playbooks found — skipped")
        return

    if missing_extends:
        for rel in sorted(missing_extends):
            report.add(f"extends missing: {rel}", False, "'extends' field required in client playbook", file=rel, rule="aurora/structure.yml")
            _gh_annotation("error", f"giskard ERROR: 'extends' missing in {rel}", rel)
    else:
        report.add(f"all client playbooks have extends ({total_files} files)", True)

    if missing_parents:
        for parent, files in sorted(missing_parents.items()):
            detail = f"playbooks/{parent}.yml missing ← " + ", ".join(files)
            report.add(f"extends target missing: {parent}", False, detail, rule="aurora/structure.yml")
            _gh_annotation("error", f"giskard ERROR: playbooks/{parent}.yml missing", files[0])
    else:
        report.add(f"all extends targets exist ({total_files} files)", True)

    if client_mismatch:
        for declared, dir_name, rel in sorted(client_mismatch):
            msg = f"declared 'client: {declared}' but in clients/{dir_name}/"
            report.add(f"client field mismatch: {declared} vs {dir_name}", None, msg, file=rel, rule="aurora/structure.yml")
            _gh_annotation("warning", f"giskard WARNING: {msg} in {rel}", rel)
    else:
        report.add(f"all client playbook client fields match dir ({total_files} files)", True)


def run(repo: Path, report: Report) -> None:
    report.section("aurora")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)

    report.section("aurora — templates")
    for check in TEMPLATE_KEY_CHECKS:
        run_check(repo, check, report)

    report.section("aurora — referential integrity")
    _check_referential_integrity(repo, report)

    report.section("aurora — playbook structure")
    _check_playbook_structure(repo, report)
