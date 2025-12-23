# CI/CD Pipeline Documentation

## Overview

The fraud detection system uses GitHub Actions for continuous integration and continuous deployment (CI/CD). The pipeline automates testing, security scanning, building, and deployment to ensure code quality and rapid delivery.

**Pipeline Features:**
- ✅ Automated testing on every pull request
- ✅ Security vulnerability scanning
- ✅ Docker image building and publishing
- ✅ Integration testing
- ✅ Automated deployment to staging and production
- ✅ Performance testing
- ✅ Dependency updates via Dependabot

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Repository                        │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  GitHub Actions Workflows                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   Lint   │  │ Security │  │   Test   │  │  Build   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│       └─────────────┴─────────────┴─────────────┘          │
│                         │                                   │
│                         ▼                                   │
│       ┌───────────────────────────────────┐                │
│       │   Integration Tests (Docker)      │                │
│       └───────────────┬───────────────────┘                │
│                       │                                     │
│           ┌───────────┴───────────┐                        │
│           ▼                       ▼                         │
│  ┌────────────────┐      ┌────────────────┐               │
│  │Deploy: Staging │      │Deploy: Prod    │               │
│  └────────┬───────┘      └────────┬───────┘               │
│           │                       │                         │
│           ▼                       ▼                         │
│  ┌────────────────┐      ┌────────────────┐               │
│  │  Smoke Tests   │      │  Smoke Tests   │               │
│  └────────────────┘      └────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflows

### 1. CI/CD Pipeline (`.github/workflows/ci-cd.yml`)

**Triggers:**
- Push to `master`, `main`, or `develop` branches
- Pull requests to these branches
- Manual workflow dispatch

**Jobs:**

#### **Lint (Code Quality)**
- Runs Black (code formatter check)
- Runs isort (import sorting check)
- Runs Flake8 (linting)

**Pass Criteria:**
- No critical linting errors (E9, F63, F7, F82)
- Complexity below 10
- Line length below 127 characters

#### **Security (Vulnerability Scanning)**
- Runs Safety (dependency vulnerability check)
- Runs Bandit (security linter)

**Pass Criteria:**
- No high-severity security issues
- No known vulnerabilities in dependencies

#### **Test (Unit & Coverage)**
- Runs pytest with PostgreSQL and Redis services
- Generates code coverage reports
- Uploads coverage to Codecov

**Pass Criteria:**
- All tests pass
- Code coverage meets threshold (configurable)

#### **Build (Docker Images)**
- Builds Docker images using Buildx
- Pushes to GitHub Container Registry (ghcr.io)
- Tags images with branch name and commit SHA

**Tags Generated:**
- `ghcr.io/org/repo/api:master`
- `ghcr.io/org/repo/api:master-abc1234`
- `ghcr.io/org/repo/api:v1.2.3` (for releases)

#### **Integration Test**
- Starts full stack with Docker Compose
- Runs integration tests
- Verifies service connectivity

**Pass Criteria:**
- All services start successfully
- Integration tests pass
- Health checks return 200 OK

#### **Deploy Staging**
- Deploys to staging environment (on `develop` branch)
- Runs smoke tests
- Notifies team

**Deployment Strategies:**
- Rolling update
- Blue-green deployment (recommended)
- Canary deployment (advanced)

#### **Deploy Production**
- Deploys to production (on `main` branch)
- Requires manual approval (environment protection)
- Runs smoke tests
- Notifies team

#### **Performance Test**
- Runs k6 load tests against staging
- Verifies performance thresholds
- Generates performance reports

**Thresholds:**
- 95th percentile response time < 500ms
- Error rate < 1%

---

### 2. Security Scanning (`.github/workflows/security-scan.yml`)

**Triggers:**
- Daily schedule (2 AM UTC)
- Pull requests modifying dependencies
- Manual workflow dispatch

**Jobs:**

#### **Dependency Scan**
- Runs Safety (PyPI vulnerability database)
- Runs pip-audit (Python package audit)

**Reports:**
- `safety-report.json`
- `pip-audit-report.json`

#### **Code Scan**
- Runs Bandit security linter
- Scans for common security issues:
  - SQL injection
  - Hardcoded passwords
  - Insecure cryptography
  - Command injection

**Severity Levels:**
- Low: Warning only
- Medium: Report but continue
- High: Fail the build

#### **Container Scan**
- Runs Trivy on Docker images
- Scans for OS and library vulnerabilities
- Uploads results to GitHub Security

**Output Formats:**
- SARIF (GitHub Security integration)
- JSON (detailed report)

#### **Secret Scan**
- Runs Gitleaks on full git history
- Detects exposed secrets:
  - API keys
  - Passwords
  - Private keys
  - AWS credentials

#### **License Scan**
- Generates license compliance report
- Flags GPL licenses (configurable)

**Allowed Licenses:**
- MIT, Apache-2.0, BSD-3-Clause
- CC0-1.0, ISC, Unlicense

---

### 3. Dependabot (`.github/dependabot.yml`)

**Automated Dependency Updates:**

**Python Dependencies:**
- Weekly updates on Mondays
- Groups minor/patch updates
- Separate PRs for major updates

**Docker Dependencies:**
- Weekly updates on Tuesdays
- Updates base images

**GitHub Actions:**
- Weekly updates on Wednesdays
- Updates action versions

---

## Setup Instructions

### 1. Initial Setup

**Required GitHub Secrets:**

Navigate to: `Settings → Secrets and variables → Actions`

```bash
# API Keys
AZURE_API_KEY=your-production-api-key

# Container Registry (auto-configured for ghcr.io)
GITHUB_TOKEN=automatically-provided

# Optional: External services
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
CODECOV_TOKEN=your-codecov-token
```

---

### 2. Environment Configuration

**Staging Environment:**

Navigate to: `Settings → Environments → New environment`

- Name: `staging`
- URL: `https://staging-fraud-detection.example.com`
- Protection rules: None (auto-deploy)

**Production Environment:**

- Name: `production`
- URL: `https://fraud-detection.example.com`
- Protection rules:
  - ✅ Required reviewers: 1-2 senior engineers
  - ✅ Wait timer: 5 minutes
  - ✅ Deployment branches: `main` only

---

### 3. Branch Protection

**For `main` branch:**

Navigate to: `Settings → Branches → Add rule`

```yaml
Branch name pattern: main

Protection rules:
  ✅ Require pull request reviews before merging (1 approval)
  ✅ Require status checks to pass before merging
    - lint
    - security
    - test
    - build
  ✅ Require conversation resolution before merging
  ✅ Require linear history
  ✅ Include administrators
```

**For `develop` branch:**

```yaml
Branch name pattern: develop

Protection rules:
  ✅ Require status checks to pass before merging
    - lint
    - test
  ✅ Require conversation resolution before merging
```

---

## Usage Guide

### Running Tests Locally

**Before pushing code:**

```bash
# 1. Lint your code
black --check .
isort --check-only .
flake8 .

# 2. Run security checks
bandit -r . --severity-level high

# 3. Run tests
pytest tests/ -v --cov

# 4. Build Docker image
docker build -f Dockerfile.api -t fraud-detection-api:test .
```

---

### Creating a Pull Request

**Workflow:**

1. **Create feature branch:**
   ```bash
   git checkout -b feature/add-new-detector
   ```

2. **Make changes and commit:**
   ```bash
   git add .
   git commit -m "feat: Add new fraud detector algorithm"
   ```

3. **Push to GitHub:**
   ```bash
   git push origin feature/add-new-detector
   ```

4. **Create PR on GitHub:**
   - Navigate to repository → Pull requests → New pull request
   - Select `develop` as base branch
   - Add description and reviewers

5. **Wait for CI checks:**
   - Lint ✅
   - Security ✅
   - Test ✅
   - Build ✅

6. **Address any failures:**
   - View workflow logs
   - Fix issues locally
   - Push new commits (CI re-runs automatically)

7. **Merge after approval:**
   - Squash and merge (recommended)
   - Delete branch after merge

---

### Deploying to Staging

**Automatic deployment on `develop` branch:**

```bash
# Merge PR to develop
git checkout develop
git pull origin develop

# Push triggers deployment
git push origin develop
```

**Monitor deployment:**
- View workflow: Actions → CI/CD Pipeline → Latest run
- Check staging: `https://staging-fraud-detection.example.com/health`

---

### Deploying to Production

**Requires manual approval:**

```bash
# 1. Merge develop to main
git checkout main
git merge develop
git push origin main

# 2. Workflow starts automatically
# 3. Navigate to: Actions → CI/CD Pipeline → Latest run
# 4. Approve deployment in "Deploy to Production" job
# 5. Monitor deployment progress
```

**Post-deployment checklist:**
- [ ] Verify health endpoint: `/health`
- [ ] Check Prometheus metrics: `/metrics`
- [ ] Review Grafana dashboards
- [ ] Monitor error rates for 30 minutes
- [ ] Notify team in Slack

---

## Troubleshooting

### Issue 1: Lint Job Failing

**Symptoms:**
- Black or isort check fails
- Flake8 reports errors

**Solutions:**

```bash
# Fix formatting automatically
black .
isort .

# Check what will change
black --diff .

# Fix specific files
black api.py detection_service.py
```

**Common Flake8 errors:**
- `E501`: Line too long → Break into multiple lines
- `F401`: Imported but unused → Remove import
- `E722`: Bare except → Use `except Exception:`

---

### Issue 2: Tests Failing in CI but Passing Locally

**Common causes:**

1. **Missing environment variables:**
   ```yaml
   # Add to workflow:
   env:
     DATABASE_URL: postgresql://test_user:test_password@localhost/test_bankdb
   ```

2. **Service not ready:**
   ```bash
   # Add wait in workflow
   - name: Wait for PostgreSQL
     run: |
       until docker-compose exec -T db pg_isready; do
         sleep 1
       done
   ```

3. **Different Python versions:**
   ```bash
   # Check local version
   python --version

   # Update workflow to match
   python-version: '3.11'
   ```

---

### Issue 3: Docker Build Failing

**Symptoms:**
- "failed to solve with frontend dockerfile.v0"
- "error building image"

**Diagnosis:**

```bash
# Build locally with verbose output
docker build -f Dockerfile.api -t test . --progress=plain

# Check for common issues:
# - Missing dependencies in requirements.txt
# - File not found (check COPY paths)
# - Base image unavailable
```

**Solutions:**

1. **Clear Docker cache:**
   ```bash
   docker builder prune -a
   ```

2. **Test build locally:**
   ```bash
   docker build -f Dockerfile.api -t fraud-detection-api:test .
   docker run --rm fraud-detection-api:test python -c "import fastapi"
   ```

---

### Issue 4: Deployment to Production Stuck

**Symptoms:**
- Workflow waiting for approval
- Deployment job not starting

**Solutions:**

1. **Check environment protection:**
   - Navigate to: Settings → Environments → production
   - Verify required reviewers are available

2. **Approve deployment:**
   - Go to: Actions → Workflow run → Deploy to Production
   - Click "Review deployments"
   - Select "production" and "Approve and deploy"

3. **Skip approval (emergency only):**
   - Temporarily remove protection rules
   - Re-run workflow

---

### Issue 5: Security Scan Reporting False Positives

**Symptoms:**
- Bandit flags safe code
- Safety reports vulnerability in dev dependency

**Solutions:**

1. **Suppress Bandit false positive:**
   ```python
   # Add comment to suppress
   password = input("Enter password: ")  # nosec B322
   ```

2. **Ignore specific Safety vulnerability:**
   ```bash
   # In workflow, add --ignore flag
   safety check --ignore 12345
   ```

3. **Update .bandit config:**
   ```toml
   # Create .bandit
   [bandit]
   exclude_dirs = ["/test", "/venv"]
   skips = ["B101", "B601"]
   ```

---

## Performance Optimization

### 1. Caching Dependencies

**Current caching:**
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
```

**Benefits:**
- Reduces pip install time from ~2min to ~30s
- Saves GitHub Actions minutes

---

### 2. Parallel Jobs

**Jobs run in parallel by default:**
- Lint + Security + Test run simultaneously
- Total time: ~5min (vs ~15min sequential)

**To add more parallel jobs:**
```yaml
jobs:
  job1:
    runs-on: ubuntu-latest
    # ...

  job2:
    runs-on: ubuntu-latest
    # Runs in parallel with job1
    # ...
```

---

### 3. Docker Build Cache

**Current caching:**
```yaml
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

**Benefits:**
- Reuses unchanged layers
- Reduces build time from ~5min to ~1min

---

## Metrics & Monitoring

### Workflow Success Rate

**View in GitHub:**
- Navigate to: Insights → Actions
- View success rate over time

**Target metrics:**
- Success rate: >95%
- Mean time to merge: <4 hours
- Deployment frequency: Daily (develop), Weekly (main)

---

### CI/CD Dashboard

**Create Grafana dashboard for CI metrics:**

```promql
# Deployment frequency
count_over_time(github_workflow_run_completed_total{workflow="CI/CD Pipeline"}[7d])

# Success rate
(
  sum(github_workflow_run_completed_total{conclusion="success"})
  /
  sum(github_workflow_run_completed_total)
) * 100

# Mean time to deploy
avg(github_workflow_run_duration_seconds{workflow="CI/CD Pipeline"})
```

---

## Best Practices

### 1. Commit Message Convention

Use conventional commits:

```bash
feat: Add new fraud detection rule
fix: Resolve database connection timeout
docs: Update API documentation
test: Add integration test for Kafka
refactor: Simplify anomaly scoring logic
perf: Optimize database query
ci: Update GitHub Actions workflow
```

**Benefits:**
- Auto-generate changelogs
- Semantic versioning
- Clear git history

---

### 2. Small, Focused PRs

**Good PR:**
- Changes 1-3 files
- Single feature or fix
- <500 lines of code
- Descriptive title and description

**Bad PR:**
- Changes 20+ files
- Multiple unrelated features
- >2000 lines of code
- "Various updates" title

---

### 3. Review Checklist

**Before approving PR:**
- [ ] All CI checks pass
- [ ] Code reviewed for logic errors
- [ ] Security implications considered
- [ ] Tests added for new features
- [ ] Documentation updated
- [ ] Breaking changes documented

---

## References

- **GitHub Actions Docs:** https://docs.github.com/en/actions
- **Docker Build Push Action:** https://github.com/docker/build-push-action
- **Codecov:** https://about.codecov.io/
- **k6 Load Testing:** https://k6.io/docs/

---

**Last Updated:** 2025-12-23
**Version:** 1.0
**Maintained By:** DevOps Team
