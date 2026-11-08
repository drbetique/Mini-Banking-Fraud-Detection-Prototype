# Roadmap

What is done, what is broken today, and what comes next. Estimates are rough working hours and include tests and documentation. The long design-level plan (security, testing and resilience upgrades with code samples) lives in [OPTIMIZATION_ROADMAP.md](OPTIMIZATION_ROADMAP.md); this file tracks the concrete work.

Legend: `[x]` done, `[ ]` planned.

## Done

- [x] **Pin SQLAlchemy below 2.1.** The requirement had no version, so installs picked up 2.1, which expects a different Postgres driver than the one the project installs. Importing `database.py` crashed with `No module named 'psycopg'`, failing every CI run and any fresh Docker build.
- [x] Add the MIT `LICENSE` file the README already advertised.
- [x] Remove stray NUL bytes from `.gitignore` that made git and GitHub treat it as a binary file.
- [x] Stop tracking two generated notes files, and ignore AI assistant instruction files.

## Next: make CI green (about 14 h)

Two tests were hidden behind the import crash above. Both are real mismatches between the tests and the code, and each needs a decision.

- [x] **Accept lowercase status values.** `test_lowercase_status_accepted` expects `"fraud"` to be accepted and normalised, but the update endpoint only allows `NEW`, `INVESTIGATED`, `FRAUD` and `DISMISSED` in capitals and returns 422 otherwise. Normalise the case before validation, in both the update body and the status filter, and cover both with tests. (2 h)
- [x] **Settle which reason a high-value transaction reports.** `test_high_value_transaction_flagged` expects "High Value" but the scorer reports "High Deviation from Avg" when both rules fire. Decide the priority, change the scorer or the test to match, and document the rule. Consider returning every triggered reason instead of one. (3 h)
- [x] **Use `docker compose` in the integration job.** The runners no longer ship the old `docker-compose` v1 binary, so the Integration Tests job failed in about a second before starting any service. The workflow now calls the `docker compose` plugin. (0.5 h)
- [ ] **Fix the nightly Security Scanning workflow.** It failed every night until 20 March 2026, after which GitHub stopped scheduling it for lack of activity. The logs have expired, so re-run it manually, read the failure and fix it. (3 h)
- [ ] **Bring the Dependabot branches up to date.** There are about a dozen open dependency-update branches, and each fails CI because it was built before the pin. Rebase or recreate them once CI is green, merging the safe ones and closing the rest. (3 h)
- [ ] **Make the installs reproducible.** Several requirements are unpinned and others are pinned. Generate a lock file (for example with `pip-compile`) and install from it in CI and in both Dockerfiles, so a new release upstream can no longer break the build overnight. (2 h)
- [ ] **Name the database driver in the URL.** Use `postgresql+psycopg2://` in the code, the CI workflow, the compose files and `.env.example`, so a change to a library's default driver cannot break the connection again. (1 h)

## Then: from the optimisation plan

The sections of [OPTIMIZATION_ROADMAP.md](OPTIMIZATION_ROADMAP.md) are the source for these; pick them up in this order once CI is green.

- [ ] **Security and authentication.** Secrets management, token-based authentication with role-based access, rate limiting and network hardening.
- [ ] **Testing infrastructure.** Integration tests for the API and performance tests for the model, wired into CI, with a coverage floor that fails the build.
- [ ] **Error handling and resilience.** Retries with exponential backoff and clearer failure reporting.

## Principles

- The main branch stays green. A red pipeline is fixed or explained before new work starts.
- A fix for a failing test either changes the code or changes the test for a stated reason; a test is never skipped to get a green tick.
- No real financial data in the repository. All sample data is synthetic.
