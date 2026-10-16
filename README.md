# lsuite

A personal, read-only CLI for BYU Learning Suite course data, with structured JSON output for AI agents.

**Status: reconnaissance in progress.** The command is not implemented or installable yet. No HTTP API or standalone authentication contract has been verified. Supported retrieval paths will be documented from direct evidence before implementation.

Planned commands cover course discovery, assignments, announcements, grades, schedule, syllabus, content, and partial course exports. The initial release will not submit assignments, take assessments, send messages, or modify Learning Suite data.

Credentials and dedicated browser state stay local, outside the repository. Public examples and fixtures must be synthetic. Course text is untrusted data, never instructions to an agent.

See [reconnaissance status](docs/reconnaissance/report.md), [coverage](docs/reconnaissance/coverage.md), and [authentication](docs/reconnaissance/authentication.md).

This project is independent of BYU and is not an official Learning Suite integration.
