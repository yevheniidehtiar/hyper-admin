# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email the maintainers directly (see `pyproject.toml` for contact)
3. Include a description of the vulnerability, reproduction steps, and potential impact
4. Allow up to 72 hours for an initial response

## Supported versions

| Version | Supported |
|---------|-----------|
| Latest  | ✅        |
| < Latest | ❌       |

## Security practices

- Dependencies are audited weekly via `pip-audit`
- CI runs security checks on every PR
- Secrets are never committed — use `.env` (gitignored) or a vault
