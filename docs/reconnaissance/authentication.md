# Authentication

Verified 2026-10-16 with a dedicated Playwright Chromium session and standalone httpx reads.

The user completes BYU CAS/SSO and MFA. The minimal verified HTTP credential is the Learning Suite `PHPSESSID` cookie, scoped to `https://learningsuite.byu.edu/`. `TAsessionID` and analytics/consent cookies were observed but were not needed for the tested reads. No password is stored by lsuite.

The import format is `{"cookies":{"PHPSESSID":"YOUR_SESSION_COOKIE"}}`. Keep it in a local file with mode 0600, or supply JSON through hidden terminal input. Never put credentials in chat or ordinary command arguments. A dedicated browser login can acquire this cookie without accessing any existing Chrome/Codex session.

A GET to `/student/top` returns a small JavaScript bootstrap. Its JSON-encoded `location.href` string leads to `/.[session]/student/top`. Resolve only that same-host target; do not execute JavaScript in the HTTP client. The authenticated document contains `instance.initialCourseGroups` with status `OK` and `data.courseGroups`. This is the validation target, including for an account with no courses. The session route prefix is transient authentication material and must never appear in output or documentation examples.

Stored credentials are plaintext, restricted to the local user (directory 0700, file 0600). Validate before atomically replacing a working session. Browser state stays in a separate dedicated directory. Logout removes local tool state and does not revoke remote BYU sessions. Expiry/refresh timing is unverified; expired authentication requires sign-in again. No automatic refresh is promised.

HTTP data requests may attach the cookie only to learningsuite.byu.edu over HTTPS. CAS is a user-login destination, not a data-request allowlist entry. Cross-host redirects must be rejected before credentials are transmitted. A login document returned with status 200 is an authentication error.
