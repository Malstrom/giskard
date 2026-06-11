# giskard

Universal zeroth rules validator for the Malstrom ecosystem.

Validates any repo against the [zeroth rules](https://github.com/Malstrom/zeroth/tree/main/rules). Optionally runs framework-specific checks.

## Checks

| Layer | Source | Always runs |
|---|---|---|
| files | `rules/files.yml` | ✅ |
| agent | `rules/agent.yml` | ✅ |
| scenarios | `rules/scenarios.yml` | ✅ |
| connections | `rules/connections.yml` | ✅ |
| framework-specific | `checks/frameworks/{name}.py` | only with `--framework` |

## Local usage

```bash
pip install pyyaml

# validate against universal rules only
python giskard.py --repo /path/to/repo

# validate + framework-specific checks
python giskard.py --repo /path/to/repo --framework dojo
```

## Add giskard to a repo

Create `.github/workflows/validate.yml` in the target repo:

```yaml
name: giskard

on:
  pull_request:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: Malstrom/giskard@main
        with:
          repo: .
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### With framework-specific checks

```yaml
      - uses: Malstrom/giskard@main
        with:
          repo: .
          framework: dojo
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

## On failure

If checks fail, giskard opens a `giskard-violation` issue in the target repo with the list of failed checks and links to the relevant rules.

Cite the issue in a Perplexity chat to trigger the fix scenario.

## Report

The full report is saved as a GitHub Actions artifact (`giskard-report`) on every run.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | all checks passed |
| 1 | one or more checks failed |
| 2 | validator error |
