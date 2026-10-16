# JSON contract, schema 1.0

Each command emits one document. `--help` is plain text. A synthetic success:

```json
{
  "schema_version": "1.0",
  "command": "assignments",
  "course": "cid-demo",
  "retrieved_at": "2026-10-16T18:00:00Z",
  "status": "ok",
  "data": [],
  "sources": ["https://learningsuite.byu.edu/cid-demo/student/home/assignments"],
  "warnings": [],
  "complete": true,
  "reason": null,
  "transport": "http"
}
```

`retrieved_at` is UTC. `course` is null when not applicable. `transport` identifies HTTP, browser combination, local operations, or no transport. `sources` contain sanitized links without transient session prefixes or parameters. Course IDs and content stable IDs remain separate from short route tokens.

Section statuses are `ok`, `unavailable`, `unsupported`, and `error`. Accessible empty lists are `ok`. Every unsuccessful section includes a reason with a code; it is incomplete. `complete` describes traversal of the documented representation, not all data that could exist elsewhere in Learning Suite. Warnings and field availability describe intentionally excluded or unexposed information.

Assignments include stable source IDs, readable descriptions, source dates, points, category references, exposed submission status, attachment references, and field availability. Grades include assignment items with available score/feedback, categories, and `overall.availability = "not_calculated"`. Schedule includes events, columns, and assignment references. Syllabus includes text and file references. Content keeps `class_information`, `learning_outcomes`, and individual `page` records distinct.

Date objects contain `source`, `iso`, and `timezone`. Source strings that parse as ISO dates/times receive an ISO value without adding an offset. Unverified numeric timestamps remain in `source` with `iso: null`. All-day dates remain dates. Refer to source labels and warnings instead of assuming a timezone.

Exports put the course record, `attempted_sections`, and the six named section results under `data`. Each result preserves status, data, sources, warnings, completeness, reason, and transport. A partial export returns exit 4 and `reason.code = "partial_export"`; successful data is retained even when another section fails.

Command/input/authentication exceptions also include an `error` object with `code`, `message`, and `exit_code`. Section retrieval failures carry their structured `reason`; inspect it even when there is no top-level exception. A single-section failure returns exit 1. An authentication error before export aggregation returns exit 3. An authentication error during aggregation is retained as a failed section in a partial export.

References contain a readable name when exposed, URL, external flag, and `access: "not_fetched"`. Their presence does not assert successful file authorization or download. Missing scalar values remain null; missing feedback is not evidence of no feedback. Course term/section details are not invented from unavailable source fields.
