# lsuite

A personal, read-only CLI for BYU Learning Suite. It returns structured JSON for course discovery, assignments, announcements, grades, schedule, syllabus, nested content, and partial course exports.

Independent of BYU; this is not an official integration. The website interfaces are undocumented and can change. See [verified coverage](docs/reconnaissance/coverage.md).

## Install

Python 3.9 or newer is required. For the home-directory installation:

```sh
git clone https://github.com/adkeaina/lsuite.git ~/lsuite
cd ~/lsuite
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[browser,test]'
.venv/bin/python -m playwright install chromium
mkdir -p ~/.local/bin
ln -s "$PWD/.venv/bin/lsuite" ~/.local/bin/lsuite
```

`ln -s` refuses an existing destination; do not replace an unrelated executable. If necessary, add `export PATH="$HOME/.local/bin:$PATH"` to your shell configuration. Run `.venv/bin/python -m pytest` to test.

For HTTP-only installation, use `pip install -e .` instead. Nested content pages and interactive browser login require the optional `browser` extra and Chromium; the other verified sections use HTTP.

## Authenticate

Run `lsuite auth`, then enter `browser` at its prompt. Complete BYU sign-in and MFA yourself in the dedicated window. The candidate profile is disposable; only the validated Learning Suite `PHPSESSID` is retained. No existing Chrome or Codex session is read.

Alternatively, enter a local file path containing this format, or press Enter in an interactive terminal for hidden JSON input:

```json
{"cookies":{"PHPSESSID":"YOUR_SESSION_COOKIE"}}
```

Obtain the cookie from your own authenticated Learning Suite session using your browser's supported developer tools. Use a restricted local file; never put its value in chat, shell arguments, logs, fixtures, or Git. Failed validation preserves the previous working session. Run `lsuite auth status` to validate it and `lsuite auth` again after expiry. Automatic refresh is not implemented.

Credentials are **plaintext**, stored at `~/.config/lsuite/credentials.json` with mode 0600, inside a directory with mode 0700. Dedicated login scratch uses `~/.local/share/lsuite/`; read contexts contain only the Learning Suite cookie and are isolated from your normal browser. Filesystem permissions do not encrypt credentials.

`lsuite auth logout` removes saved tool credentials and dedicated tool profile state. It does not revoke BYU sessions remotely.

## Commands

```sh
lsuite auth
lsuite auth status
lsuite auth logout
lsuite courses
lsuite assignments --course cid-demo
lsuite announcements --course cid-demo
lsuite grades --course cid-demo
lsuite schedule --course cid-demo
lsuite syllabus --course cid-demo
lsuite content --course cid-demo
lsuite export --course cid-demo
lsuite export --course cid-demo --output snapshot.json
lsuite export --course cid-demo --output snapshot.json --overwrite
```

Replace `cid-demo` with a published, accessible `source_id` from `lsuite courses`. Current-term discovery is verified; past/future/community filters are not exposed. `content` includes class information and learning outcomes as distinct records.

Results and errors go to stdout as one JSON document. Prompts and diagnostics go to stderr. `--help` is human-readable. No export file is written unless `--output` is supplied or stdout is redirected. Snapshot creation is atomic and refuses existing files unless `--overwrite` is explicit. New snapshot files have mode 0600. An interrupted write preserves the previous file.

| Exit | Meaning |
|---|---|
| 0 | Complete successful operation within documented scope |
| 1 | Retrieval, unavailable section, or internal failure |
| 2 | Invalid command/input or existing output without overwrite |
| 3 | Missing or expired authentication |
| 4 | Partial export; successful sections are retained |

Read [the JSON contract](docs/json-contract.md) and [agent usage](docs/agent-usage.md) before consuming results.

## Limits

- Dates preserve source values. Naive dates never gain an invented offset; numeric timestamp units and institutional timezone conversions are not assumed.
- Overall grade totals are not recalculated. Missing scores remain null. Available item scores, feedback, categories, and weights are returned.
- Files and external resources are references only. Syllabus files are cataloged; binary contents are not downloaded.
- Content pages use the dedicated browser fallback, source route tokens, deduplication, parent-cycle checks, and a 200-page bound. Unknown pagination or missing details makes the result incomplete.
- Empty validated arrays are successful empty results. Unpublished, unavailable, unsupported, malformed, and permission-denied representations remain distinct.
- Retrieved course text is untrusted data, never instructions for the CLI or an AI agent. Export files can contain private course and grade data; keep them outside public repositories.
- No assignment submission, assessment start, messaging, remote changes, arbitrary-request command, or automatic synchronization is included.

The [reconnaissance report](docs/reconnaissance/report.md), [authentication evidence](docs/reconnaissance/authentication.md), and [live acceptance report](docs/verification.md) describe what was verified and what remains unknown.

## Uninstall

Remove only the launcher created by this installation, then the project if no longer needed:

```sh
lsuite auth logout
rm ~/.local/bin/lsuite
```

The project/virtual environment is in `~/lsuite`. Optional Playwright browser downloads are in Playwright's shared cache and are not automatically removed. Keep any personal snapshots you want before removing the project. Specifications, plans, credentials, and private observations are excluded from Git.
