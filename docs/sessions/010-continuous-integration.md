# Session 010 - Continuous Integration with GitHub Actions

**Date:** 2026-09-01

**Status:** Complete

## Objective

Turn the existing automated test suite into repeatable repository verification
for pushes and pull requests involving the `main` branch.

## What we built

- A GitHub Actions workflow at `.github/workflows/tests.yml`.
- Push and pull-request triggers for `main`.
- A `test` job running on a clean GitHub-hosted Ubuntu runner.
- Python 3.11 setup matching the application container.
- Pip dependency caching and installation from `requirements.txt`.
- Automatic execution of `python -m pytest -q`.

## Concepts learned

- Continuous integration automatically verifies repository changes at defined
  integration events.
- GitHub discovers workflow definitions specifically under
  `.github/workflows/`.
- The `on` section defines when a workflow runs.
- Jobs select runners, and steps execute reusable actions or shell commands.
- A GitHub-hosted runner is a temporary clean machine, independent of the local
  development environment.
- Program exit codes determine whether workflow steps succeed or fail.
- CI performs checks; repository rules decide whether those checks are mandatory.
- YAML files have meaning only to the system that discovers and interprets them.

## Workflow lifecycle

```text
Push or pull request involving main
    -> GitHub discovers .github/workflows/tests.yml
    -> the configured event trigger matches
    -> GitHub allocates an Ubuntu runner
    -> actions/checkout downloads the triggering commit
    -> actions/setup-python configures Python 3.11
    -> pip installs requirements.txt
    -> pytest runs the automated suite
    -> GitHub records a passing or failing status
```

## Design decisions

- Start with the existing isolated pytest suite rather than full Docker Compose
  integration tests.
- Match CI and Docker on Python 3.11.
- Run for direct pushes to `main` and pull requests targeting `main`.
- Keep the workflow small so each trigger, job, action, and command is explicit.
- Continue using feature branches and green checks as a manual working practice
  when repository rules cannot enforce them.

## Repository-rule limitation

A `Protect main` ruleset was designed with pull-request and required `test`
check rules. GitHub reported that rulesets are not enforced for this private
repository on the current account plan without moving to a GitHub Team
organization account. No upgrade is planned. CI remains fully operational, but
the green check is a reported guardrail rather than an enforced merge gate.

## Files changed

- `.github/workflows/tests.yml`
- `README.md`
- `docs/sessions/README.md`
- `docs/sessions/TIMELINE.md`
- `docs/sessions/010-continuous-integration.md`

## Verification

- `python -m pytest -q` completed locally with 27 passed tests and one existing
  third-party Starlette pending-deprecation warning in 2.41 seconds.
- GitHub Actions workflow run `#1` completed successfully in 17 seconds.
- Checkout, Python setup, dependency installation, and test execution all
  succeeded on the GitHub-hosted Ubuntu runner.

## Blockers

- Required pull requests and status checks cannot be enforced for this private
  repository on the current GitHub account plan.
- The limitation does not prevent the CI workflow from running or reporting
  results.

## Next checkpoint

Add basic operational metrics and documentation so operators can inspect the
platform's health and processing behavior beyond individual API responses.
