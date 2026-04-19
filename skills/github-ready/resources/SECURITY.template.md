# Security Policy for {{package_name}}

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please email us directly. Do not open a public issue.

Please include as much detail as possible to help us understand and reproduce the issue:

- A clear description of the vulnerability
- Steps to reproduce the issue
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)

We will investigate all reports and aim to respond within 48 hours.

## Security Best Practices

When using this package:

1. Keep dependencies up to date
2. Review the code before using in production
3. Report any security concerns promptly
4. Follow secure coding practices when extending functionality

## Dependency Security

This package depends on third-party libraries. We regularly audit dependencies for known vulnerabilities using:

- `pip-audit` - Check for vulnerable dependencies
- `safety` - Check for known security issues
- `bandit` - Security linting for Python code

Run security scans before deployment:

```bash
pip-audit
safety check
bandit -r .
```
