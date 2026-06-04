# API Reference

## Technical Routes

Technical routes do not use the public select contract.

```text
GET /livez
GET /readyz
GET /
```

## Selection Routes

Plugin routes are mounted under:

```text
/api/v1
```

Selection endpoints return:

```json
[
  {"label": "Human label", "value": "stable-value"}
]
```

## Admin Routes

```text
GET /api/v1/admin/plugins
GET /api/v1/admin/routes
GET /api/v1/admin/settings
```
