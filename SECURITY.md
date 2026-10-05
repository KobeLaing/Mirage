# Security Policy

Mirage is a local side project. **It is not ready to be exposed to the internet**:
it has no real authentication and no content moderation (see
[docs/threat-model.md](docs/threat-model.md#5-known-gaps-and-accepted-risks)).

## Reporting a vulnerability

Please don't open a public issue for security problems. Report them privately
through GitHub's **Security → Report a vulnerability** (private vulnerability
reporting) on this repository. Include steps to reproduce and the impact you
expect. You should get a reply within 7 days.

## Supported versions

Only the latest commit on the default branch is supported.

## What's in place

- Threat model and abuse cases: `docs/threat-model.md`, `docs/requirements.md`
- CI on every push and pull request: tests (including security tests), Bandit,
  pip-audit, npm audit, and Gitleaks secret scanning, with read-only permissions
- Dependabot for pip, npm, and GitHub Actions
- Pinned dependency versions and SHA-pinned CI actions
