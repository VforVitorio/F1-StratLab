# Audit records

This is an agent-assisted audit archive. Reports are evidence from a dated review, not automatically current findings. Check the cited code, data, and issue before acting on a recommendation.

- `GATE_*` records a verification gate, usually tied to a change or issue.
- `AUDIT_*` records a broader code or design review.
- `MEASURE_*` pairs a human-readable result with structured data when both exist.
- `TRACE_*` records runtime evidence; `REVIEW_*` records adjudication; `FIX_*` records a change and its verification.
- `*_LOG` files are chronological records. Keep them append-only when later runs need the earlier sequence.

Files are kept at their current paths because issues, pull requests, scripts, tests, and other audits link to them. A result marked historical or superseded can still be useful evidence; its date and scope determine how to read it.
