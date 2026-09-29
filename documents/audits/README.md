# Audit records

These agent-assisted reviews record a particular code, data, or runtime snapshot. A finding may be stale; check its date, cited source, and issue before acting on it.

- `assessments/` contains code and design audits.
- `gates/` contains issue and change verification reports.
- `measurements/` contains results and their structured data.
- `reviews/` contains independent and adjudication reviews.
- `fixes/`, `designs/`, `traces/`, `sweeps/`, and `implementation/` contain change records, proposals, runtime captures, repository scans, and implementation notes.

Filenames use a short topic and retain an issue or audit ID where it helps locate the evidence. A few open-issue reports remain in this directory while their issue branches carry pending edits. Traces and measurement data stay beside their reports when scripts or tests consume them.
