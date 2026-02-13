# Caliente Scheduler Backend

## Quick Reference
- API documentation: see `docs/API_REFERENCE.md`
- Models: `src/core/api/models.py`
- Serializers: `src/core/api/Serializers/`
- Viewsets: `src/core/api/Viewsets/`
- Auth endpoints: `src/core/api/urls_auth.py`
- Auto-router: `src/core/utils/router_utils.py`

## Tech Stack
- Django 6.0.1 + DRF 3.16.1
- PostgreSQL (psycopg 3.3.2)
- SimpleJWT 5.4.0 (JWT auth + token blacklist)
- drf-spectacular 0.29.0 (OpenAPI docs)
- django-cors-headers 4.7.0

## Project Structure
```
src/core/
  api/
    models.py          — All 13 models
    Serializers/        — One file per model + auth_serializers.py
    Viewsets/           — One file per model + auth_viewset.py
    urls.py             — Auto-registered model routes
    urls_auth.py        — Manual auth routes
    services/           — Email service
  core/
    settings.py         — Django settings
    urls.py             — Root URL config
  utils/
    router_utils.py     — Auto-viewset registration
```

## Conventions
- UUIDs for public-facing IDs, sequential PKs internally
- `fields = '__all__'` on model serializers
- Auto-router pluralizes ViewSet names for endpoints
- Singleton pattern for SystemSettings (pk=1)
- JSONField for edit_history, shift_order, algorithm logs
