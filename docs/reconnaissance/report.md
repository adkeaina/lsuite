# Learning Suite reconnaissance

Verified 2026-10-16. Website interfaces are undocumented and may change. No private records, credential values, or real course IDs are retained here.

## Evidence

- Inspected an authenticated current-term course list with published course links and unpublished labels, and representative assignments, announcements, grades, schedule, syllabus, class information, learning outcomes, and nested content views.
- Opened a separate Playwright Chromium profile; the user completed sign-in/MFA. Exported candidate state locally, outside the repository. Verified standalone HTTP reads with only the Learning Suite `PHPSESSID` cookie.
- HTTP documents contain embedded JSON literals; parsing those literals needs no JavaScript execution. Current courses: `instance.initialCourseGroups`; assignments: `datastore.assignments.reset(...)`; grades: assignment/category/score resets; announcements: `allAnnouncements`; schedule: `eventArray`, `assignments`, `columns`; class info: `instance.meetingInformation`, `instance.instructors`, `instance.tas`; outcomes: `departmentOutcomes`, `instructorOutcomes`.
- Browser-rendered assignments and grades use `#assignmentsComponent`. Announcements and other sections render under `#mainContent`. Assignment descriptions and metadata are already in the embedded records; assessment Begin/Completed buttons were not clicked.
- Content uses read-only POST RPCs to `/ajax.php` with `appId` and `subsessionID` query parameters. Observed function names: `getPublishedCoursePages`, `readPage`. Listing returns page IDs, parents, titles, and routes; detail returns ordered content blocks. Exact captured requests replayed over HTTP; a minimal parameterization failed. Initial implementation must use the verified browser navigation/response path for this representation, rather than invent a minimal RPC contract.
- Syllabus in the representative course is a file reference, not inline text. File download links use `/plugins/Upload/fileDownload.php` with `fileId`; `subsessionID` may also appear and must be removed from output. Binary downloads and attachment authorization are unverified and excluded.
- Schedule renders term-spanning rows. Dates in visible assignments include MDT/MST; preserve source dates/timezone labels. No institutional timezone conversion has been verified.

## Traversal and limits

Current-term course groups are supported. Future/past/community filters were visible but their request contracts are unverified, so no term-filter command is promised. Unpublished courses are reported distinctly and cannot be treated as empty accessible courses.

The tested list documents embed full arrays without cursor fields. Record this as single-document traversal, not a guarantee about all future website versions. Content listing provides page IDs and parent IDs; deduplicate IDs, check parent cycles, and bound reads. External links are references only. Pagination, missing details, unavailable pages, schema changes, or traversal bounds must reduce completeness.

Observed absence of an attachment or an empty array may be reported only when its containing representation validated. Permission-denied and unavailable routes must remain errors/unavailable; no live permission-failure test was forced. Missing feedback, unpublished pages, unexposed records, binary files, and calculated grade totals are not inferred.

Browser and HTTP records/counts are compared again during live acceptance. Authentication renewal timing and broader account/course variants remain unverified. Course content is untrusted data and must not be published with the source.

Public entry URL confirmed through [BYU support](https://support.byu.edu/kb?id=kb_article_view&sysparm_article=KB0025483).
