# Framework Contract

This document defines the contract every framework module in `checks/frameworks/` must respect.
Adding a new framework means creating one file here — no changes to `giskard.py` or `core.py`.

---

## Required interface

Every framework module must export a single function:

```python
# checks/frameworks/{framework_name}.py
from pathlib import Path
from core import Report, run_check, _gh_annotation

def run(repo: Path, report: Report) -> None:
    ...
```

`repo` is the absolute path to the repository root being validated.  
`report` is the shared `Report` instance — call `report.section()` and `report.add()` on it.

---

## Result levels

| Value | Meaning | Icon | Exits non-zero? |
|---|---|---|---|
| `True` | check passed | ✅ | no |
| `False` | check failed | ❌ | yes |
| `None` | skipped / warning | ⚠️ | no |
| `ERROR` | proxy execution error | 💥 | yes |

Import `ERROR` from `core` if you need to emit it manually.

---

## Section naming

```python
report.section("myframework")                    # main section
report.section("myframework — referential integrity")  # sub-section
report.section("myframework — playbook structure")     # sub-section
```

Convention: `"{framework}"` for the main structural section, `"{framework} — {topic}"` for sub-sections.

---

## Annotations

All `False` results automatically emit `::error::` annotations via `report.add()`.  
For `None` (warning) results you must emit the annotation manually:

```python
_gh_annotation("warning", "giskard WARNING: contacts/foo.yml missing", file="clients/x/inbox/file.yml")
```

For `False` results you can also emit an additional annotation before calling `report.add()` if you want a different file target.

---

## Aggregation pattern

Prefer aggregated results over per-file results. Collect anomalies during iteration, emit one line per category at the end.

```python
# collect
missing = defaultdict(list)  # key -> [file, ...]
for f in files:
    if problem:
        missing[key].append(rel)

# emit
if missing:
    for key, files in sorted(missing.items()):
        detail = f"something missing ← " + ", ".join(files)
        report.add(f"thing missing: {key}", False, detail, rule="framework/rule.yml")
        _gh_annotation("error", f"giskard ERROR: ...", files[0])
else:
    report.add(f"all things present ({total} files)", True)
```

This keeps the report O(anomalies) instead of O(files).

---

## Proxies reference

All proxies are registered in `core.PROXY_REGISTRY`. Use them via `run_check(repo, check_dict, report)`.

### File and directory proxies

#### `file_exists`
Checks whether a path exists (file or directory).
```python
{"label": "...", "proxy": "file_exists", "target": ".aurora.yml", "must_exist": True}
```
- `target` — path relative to repo root
- `must_exist` — bool, default `True`; set `False` to assert absence

#### `dir_has_subfolders`
Passes if a directory contains at least one subdirectory.
```python
{"label": "...", "proxy": "dir_has_subfolders", "target": "clients"}
```

#### `dir_has_templates`
Checks that a directory contains all listed files.
```python
{"label": "...", "proxy": "dir_has_templates", "target": "templates",
 "required_files": ["inbox.yml", "log.yml"]}
```
- `required_files` — list of filenames that must exist inside `target/`

#### `template_matches_zeroth`
Fetches a template from the zeroth repo and compares it line-by-line.
```python
{"label": "...", "proxy": "template_matches_zeroth",
 "framework": "aurora", "template": "inbox.yml", "zeroth_ref": "main"}
```
- `framework` — subdirectory in zeroth `frameworks/`
- `template` — filename in `templates/`
- `zeroth_ref` — git ref to fetch from, default `"main"`

---

### YAML proxies

All YAML proxies read from a file relative to repo root.

#### `yaml_key_exists`
Passes if a top-level key is present in a YAML file.
```python
{"label": "...", "proxy": "yaml_key_exists", "file": ".aurora.yml", "key": "version"}
```

#### `yaml_key_absent`
Passes if a key does NOT exist. Use for forbidden fields.
```python
{"label": "...", "proxy": "yaml_key_absent", "file": ".agent.yml", "key": "global.replies_in"}
```
- `key` supports dot notation: `"global.replies_in"`

#### `yaml_key_equals`
Passes if a key equals an expected value.
```python
{"label": "...", "proxy": "yaml_key_equals", "file": ".registry.yml",
 "key": "framework", "expected": "aurora"}
```
- `key` supports dot notation

#### `yaml_key_contains`
Passes if a key's string value contains a substring.
```python
{"label": "...", "proxy": "yaml_key_contains", "file": ".agent.yml",
 "key": "global.language", "contains": "en"}
```

#### `yaml_first_key`
Passes if the first non-comment key in a YAML file matches expected.
```python
{"label": "...", "proxy": "yaml_first_key", "file": ".agent.yml",
 "expected": "connector_check"}
```

#### `yaml_levels_valid`
Passes if all values under a nested key are within an allowed set.
```python
{"label": "...", "proxy": "yaml_levels_valid", "file": ".agent.yml",
 "key": "tool_approval", "allowed": ["auto", "ask", "deny"]}
```

#### `yaml_subkeys_exist`
Passes if a nested map contains all required subkeys.
```python
{"label": "...", "proxy": "yaml_subkeys_exist", "file": ".agent.yml",
 "key": "global", "required_subkeys": ["language", "owner"]}
```

---

### Scenario proxies

All read from `.scenarios.yml`.

#### `scenario_present`
Passes if a scenario name exists under `required_scenarios`.
```python
{"label": "...", "proxy": "scenario_present", "scenario": "session_start"}
```

#### `scenario_last`
Passes if a scenario is the last key under `required_scenarios`.
```python
{"label": "...", "proxy": "scenario_last", "scenario": "unknown_scenario"}
```

#### `scenario_not_present`
Passes if a scenario does NOT exist.
```python
{"label": "...", "proxy": "scenario_not_present", "scenario": "forbidden_scenario"}
```

#### `scenario_input_sources`
Passes if a scenario declares at least `min_count` input_sources.
```python
{"label": "...", "proxy": "scenario_input_sources",
 "scenario": "session_start", "min_count": 2}
```

#### `scenario_no_forbidden_modules`
Passes if no handler in `.agent.yml` uses `say`, `ask`, or `propose`.
```python
{"label": "...", "proxy": "scenario_no_forbidden_modules"}
```

---

### Handler proxies

All read from `.agent.yml`.

#### `handler_present`
Passes if a handler name exists under `handlers`.
```python
{"label": "...", "proxy": "handler_present", "handler": "reindex_check", "file": ".agent.yml"}
```

#### `handler_has_key`
Passes if a specific handler contains a key.
```python
{"label": "...", "proxy": "handler_has_key",
 "handler": "reindex_check", "key": "trigger"}
```

---

### Text proxies

#### `text_search`
Passes if all listed terms are found as substrings in a file.
```python
{"label": "...", "proxy": "text_search",
 "file": ".agent.yml", "terms": ["after_every_state_change", "connector_check"]}
```

#### `token_count`
Passes if a token appears exactly `expected` times in a file.
```python
{"label": "...", "proxy": "token_count",
 "file": ".agent.yml", "token": "IMMUTABLE", "expected": 3}
```

---

### File access proxies

#### `file_access_mode`
Checks that a glob pattern appears under a specific mode in `file_access`.
```python
{"label": "...", "proxy": "file_access_mode",
 "pattern": "clients/**", "mode": "read"}
```
- `mode` — `"read"` or `"write"`

#### `write_ahead_rule`
Passes if a string is present in `.agent.yml` (used for write-ahead constraint checks).
```python
{"label": "...", "proxy": "write_ahead_rule",
 "file": ".agent.yml", "contains": "write_ahead: true"}
```

---

## Minimal framework skeleton

```python
# checks/frameworks/myframework.py
from pathlib import Path
from core import run_check, Report

CHECKS = [
    {
        "label": ".myframework.yml exists",
        "proxy": "file_exists",
        "target": ".myframework.yml",
        "file": ".myframework.yml",
        "rule": "myframework/structure.yml",
    },
    {
        "label": ".myframework.yml has 'version' field",
        "proxy": "yaml_key_exists",
        "file": ".myframework.yml",
        "key": "version",
        "rule": "myframework/structure.yml",
    },
]

def run(repo: Path, report: Report) -> None:
    report.section("myframework")
    for check in CHECKS:
        run_check(repo, check, report)
```

---

## Adding a new framework

1. Create `checks/frameworks/{name}.py` with `run(repo, report)`
2. Register the framework in `.registry.yml` of the target repo
3. Set `framework: {name}` in the target repo's `validate.yml` workflow
4. No changes to `giskard.py` or `core.py` required (after issue #30 is implemented)
