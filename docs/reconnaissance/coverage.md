# Retrieval coverage

Verified 2026-10-16; all rows require the local PHPSESSID session. See authentication.md for session bootstrap. Sources shown without transient prefixes or real IDs.

| Section | Source | Observed fields | Transport | Traversal / limits |
|---|---|---|---|---|
| courses | /student/top | Current group term, course title, publication, href | HTTP embedded initialCourseGroups | Single document; unpublished rows retained |
| assignments | /cid-COURSE/student/home/assignments | IDs, titles, descriptions, dates, points, categories, student action | HTTP embedded assignment/category arrays | Details embedded; do not start assessments |
| announcements | /cid-COURSE/student/home/announcements | ID, title/body, author/date where exposed | HTTP allAnnouncements | One embedded array |
| grades | /cid-COURSE/student/gradebook | Assignments, category weights, item scores, notes | HTTP embedded assignment/category/score arrays | Computed overall totals not reproduced |
| schedule | /cid-COURSE/student/calendar | Events, server dates, columns, assignment dates | HTTP embedded eventArray/assignments/columns | Single document; no invented offsets |
| syllabus | /cid-COURSE/student/syllabus | Inline text or download reference | HTTP #mainContent | Binary contents not fetched |
| content | /cid-COURSE/student/pages[/id-PAGE] | Page ID, parent, title, ordered content blocks | Dedicated browser response inspection | Bounded deduplicated traversal; detect parent cycles |
| class information | /cid-COURSE/student/home/info | Meetings, instructors, teaching assistants | HTTP instance JSON fields | Distinct content record |
| learning outcomes | /cid-COURSE/student/home/outcomes | Department and instructor outcomes | HTTP embedded outcome arrays | Distinct content record |

Files: catalog available links only; remove session parameters. External resources are never fetched. Credentials: PHPSESSID on the sole data host learningsuite.byu.edu. No verified cursor pagination in observed documents. Unknown representations fail explicitly; they never become empty lists.
