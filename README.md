# giskard

> "A robot must not harm zeroth law."

Framework validator for the Malstrom ecosystem.
Giskard reads `zeroth` rules and validates that a repo is a conforming framework instance.

## How it works

1. You point giskard at a repo and declare which framework it claims to be
2. Giskard reads the corresponding `zeroth/frameworks/{name}/checklist.yml`
3. It checks the repo structure and `.agent.yml` against the checklist
4. It returns a pass/fail report with details on every failed item

## Usage

### As a GitHub Action (in your framework repo)

```yaml
# .github/workflows/validate.yml
name: Validate framework
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Malstrom/giskard@main
        with:
          framework: dojo
```

### As a CLI

```bash
pip install pyyaml
python giskard.py --framework dojo --repo /path/to/repo
```

## Registered frameworks

| Framework | Checklist |
|-----------|----------|
| dojo | [zeroth/frameworks/dojo/checklist.yml](https://github.com/Malstrom/zeroth/blob/main/frameworks/dojo/checklist.yml) |
| tensho | [zeroth/frameworks/tensho/checklist.yml](https://github.com/Malstrom/zeroth/blob/main/frameworks/tensho/checklist.yml) |
| sudo-hire-me | [zeroth/frameworks/sudo-hire-me/checklist.yml](https://github.com/Malstrom/zeroth/blob/main/frameworks/sudo-hire-me/checklist.yml) |
