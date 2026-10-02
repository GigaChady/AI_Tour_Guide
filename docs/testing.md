# Testing strategy

The project uses five complementary test types for the AI, Backend, and Mobile parts of the system.

## 1. Unit tests

Unit tests verify isolated application logic.

- Backend: `pytest Backend/tests --ignore=Backend/tests/e2e`
- AI: `pytest AI/tests`
- Mobile: `./gradlew testDevDebugUnitTest` from `Mobile/android`

## 2. End-to-end smoke tests

Backend E2E smoke tests run against the CI Docker Compose stack with Backend, AI in mock mode, PostgreSQL, Redis, and MinIO.

Local command:

```bash
docker compose -f docker-compose.ci.yml up -d --build api ai
```

```bash
docker compose -f docker-compose.ci.yml exec -T -e E2E_TESTS=1 api pytest tests/e2e
```

Stop the stack after the test:

```bash
docker compose -f docker-compose.ci.yml down -v --remove-orphans
```

## 3. Static security testing

Bandit scans Python source code in Backend and AI for common security issues.

```bash
bandit -r Backend AI -x "*/tests/*" --severity-level medium
```

## 4. Dependency vulnerability scanning

`pip-audit` checks Python dependency files for known vulnerabilities. Dependabot is also configured for Backend, AI, and Mobile dependency updates.

```bash
pip-audit --ignore-vuln CVE-2024-23342 -r Backend/requirements.txt
pip-audit --ignore-vuln CVE-2024-23342 -r AI/requirements.txt
```

## 5. Performance smoke testing

Locust sends a short, low-volume load against stable Backend endpoints running from the CI Docker Compose stack. The stack also starts AI in mock mode. This is a CI smoke test, not a production benchmark.

Local command:

```bash
docker compose -f docker-compose.ci.yml up -d --build api ai
```

```bash
docker compose -f docker-compose.ci.yml run --rm locust
```

Stop the stack after the test:

```bash
docker compose -f docker-compose.ci.yml down -v --remove-orphans
```

All five test types are integrated in `.github/workflows/tests.yml`.
