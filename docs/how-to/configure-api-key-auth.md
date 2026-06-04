# Configure API Key Authentication

Aperture can protect API routes with API keys.

## YAML Example

```yaml
auth_mode: api_key
api_key_header: X-API-Key
api_keys:
  internal-tool: "change-me"
auth_skip_paths:
  - /
  - /docs
  - /openapi.json
  - /livez
  - /readyz
```

## Helm Example

Keep API keys in an existing Kubernetes Secret:

```yaml
auth:
  mode: api_key
  apiKeys:
    existingSecret: aperture-api-keys
    existingSecretKey: APT_API_KEYS
```

The Secret value must be a JSON object:

```json
{"internal-tool": "change-me"}
```

## Skip Paths

`auth_skip_paths` supports exact paths and a trailing `/*`.

```yaml
auth_skip_paths:
  - /livez
  - /readyz
  - /api/v1/demo/*
```

`/api/v1/demo/*` matches `/api/v1/demo` and every route under it.
