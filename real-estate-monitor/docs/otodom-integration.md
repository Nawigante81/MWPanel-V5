# Otodom integration (production)

## Required ENV

```env
CRM_AUTH_SECRET=
CRM_BOOTSTRAP_TOKEN=
CRM_DEFAULT_ADMIN_PASSWORD=

OTODOM_API_BASE_URL=
OTODOM_CLIENT_ID=
OTODOM_CLIENT_SECRET=
OTODOM_ACCESS_TOKEN=
OTODOM_REFRESH_TOKEN=
OTODOM_ACCOUNT_ID=
OTODOM_DEFAULT_CONTACT_NAME=
OTODOM_DEFAULT_CONTACT_EMAIL=
OTODOM_DEFAULT_CONTACT_PHONE=
OTODOM_REQUEST_TIMEOUT=30000
OTODOM_MAX_RETRIES=5
```

## Deployment checklist

1. `alembic upgrade head`
2. configure ENV secrets
3. start API + Celery worker + Celery beat
4. run admin bootstrap
5. create property + images
6. call publish endpoint

## Bootstrap admin

- check status: `GET /auth/bootstrap-status`
- create first admin:

```bash
curl -X POST "$API/auth/bootstrap-admin" \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Token: $CRM_BOOTSTRAP_TOKEN" \
  -d '{"email":"admin@domain.pl","password":"StrongPass!123","name":"Admin"}'
```

## Publish first listing to Otodom

1. login and get Bearer token
2. create property: `POST /properties`
3. add images: `POST /properties/:id/images`
4. publish: `POST /api/properties/:id/publish/otodom`
5. process queue (if needed manually): `POST /api/publications/otodom/process-jobs`
6. inspect status/logs:
   - `GET /api/properties/:id/publication/otodom`
   - `GET /api/properties/:id/publication/otodom/logs`

## Troubleshooting

- `publish_error` + missing fields => check validator output and complete property data
- `401` Otodom => verify tokens; refresh is automatic if refresh credentials exist
- image upload errors => verify image URLs are publicly reachable by Otodom API
- retries/backoff tracked in `publication_jobs` and audit logs
