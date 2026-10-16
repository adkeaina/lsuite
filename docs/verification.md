# Verification

Executed 2026-10-16 on macOS arm64 using Python 3.9.6, an isolated project virtual environment, and optional Playwright Chromium.

## Automated checks

`python -m pytest -q`: 72 passing tests after the final branch review and regression fixes. Coverage includes the JSON schema, UTC retrieval timestamps, source-date preservation, failed credential replacement, storage modes, login HTML with HTTP 200, login redirects, cross-host redirects, attachment-source rejection, timeouts, bounded retries, rate limits, permission failures, local browser fixtures, section parsing, unpublished courses, explicit empty/unsupported results, content cycles, unexpected cursor markers, stable-ID/route-token distinctions, mixed exports, interrupted writes, exclusive no-overwrite races, and CLI stdout/stderr separation.

The console-script help, authentication JSON, and invalid-input JSON were checked from a directory outside the project. The user launcher resolves to the virtual-environment script and is on the checked shell's PATH.

## Read-only live acceptance

The user completed BYU login/MFA in a dedicated browser. Standalone HTTP validation succeeded with only PHPSESSID. Each installed command was run from outside the project, with output parsed in memory. No private JSON response was saved in the project or committed.

| Check | Result |
|---|---|
| Authentication status | Successful validation |
| Current courses | 8 records, including 4 published courses |
| Assignments | 60 records |
| Announcements | 1 record |
| Grades | 60 assignment items and 5 categories |
| Schedule | 28 event entries, 60 assignment references, 2 columns |
| Syllabus | 1 cataloged file reference |
| Content | 5 pages, separate class information, separate learning outcomes |
| Combined export | All 6 sections successful, complete within documented scope |

Source links were checked for transient session-prefix/parameter leakage. Credentials have mode 0600 within a 0700 directory. Tracked public files were scanned against the actual saved cookie value; no matches or tracked specs/plans/private scratch were found.

The HTTP assignment count matches the inspected website list. All 60 assignment titles matched the rendered browser list after rendering completed, and the syllabus reference count matched; account values were not persisted. The syllabus file reference matches the browser representation. Overall grade calculations, file downloads/authorization, account expiry timing, other course variants, and unverified past/future/community filter behavior are not claimed as tested.

A partial-export fixture confirms that a failed section retains successful ones and returns exit 4. Live server permission/rate-limit failures were not induced; those failure paths use synthetic transport fixtures.

## Review

A separate whole-branch author review was completed against the plan, spec, review-focus cases, source diff, tests, and live evidence. Five findings were fixed with regression tests watched failing before passing: encoded session URL redaction, unverified browser writes/navigation, malformed content retention, exposed course-section metadata, and deferred browser body rendering. The final suite passed 72 tests, and all installed live commands plus combined export passed again after the fixes.

No subagent was used, per the user's instruction. This author review is weaker than an independent fresh-context review. No unresolved important findings or deferred minors were identified.
