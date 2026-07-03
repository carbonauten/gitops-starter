# Workflow & Audit — Sprint 6

## Article workflow

```
draft ──submit──► review ──approve──► published
                    │                      ▲
                    │                      │
                    └──schedule approve──► scheduled ──scheduler──┘
                    │
                    └──reject──► rejected ──edit+submit──► review
```

- **Editors** save drafts and submit for review.
- **IT master** approves (immediate or scheduled), or rejects with comment.
- **Scheduled** articles are published automatically every 60 seconds when due.

API:

- `POST /api/workflow/articles/{id}/submit`
- `POST /api/workflow/articles/{id}/approve` — body: `{ "scheduled_publish_at": "..." }` optional
- `POST /api/workflow/articles/{id}/reject` — body: `{ "comment": "..." }`

## Certificate renewal approval

1. Editor enables **Renewal in progress** and saves.
2. Editor clicks **Request renewal approval**.
3. **IT master** or **certificate_manager** approves/rejects on `/workflow`.

## Roles

| Role | Permissions |
|------|-------------|
| `it_master` | Full admin, approvals, audit, users |
| `editor` | Create/edit content, submit for review |
| `certificate_manager` | Edit content + approve certificate renewals |
| `viewer` | Read-only |

## Audit log

`GET /api/audit` (IT master) — all create/update/delete and workflow actions.

## Monitoring

`GET /api/monitor/summary` (IT master) — health, sync, workflow queue, expiring certs, recent audit.
