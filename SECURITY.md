# Security Policy

## Reporting a vulnerability

Camel AI automates real software and can hold login sessions, so we take security
seriously. **Please do not open a public issue for security problems.**

Instead, use GitHub's private **[Report a vulnerability](https://github.com/DilawarShafiq/camel-ai/security/advisories/new)**
flow, or email the maintainer. We aim to acknowledge within a few days.

## Scope & good practice

- Camel AI runs **locally** and only automates software **you** are authorized to use.
- API keys are stored in `~/.camel/config.json` on your machine — never commit it.
- The only external API Camel AI calls is your chosen **LLM** endpoint.

## Supported versions

The latest release on `main` receives fixes.
