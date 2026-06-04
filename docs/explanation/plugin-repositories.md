# Plugin Repositories

Aperture core stays small on purpose.

The core repository owns:

- the FastAPI runtime
- settings
- auth
- logging
- cache helpers
- plugin loading
- the internal `admin` plugin
- Helm and delivery tooling

Business plugins live in separate repositories.

Examples:

- an AWS plugin repository
- a GitLab plugin repository
- an internal CMDB plugin repository
- a data.gouv.fr demo or training plugin repository

This keeps Aperture stable while plugins can move at their own speed.

## Why Plugins Live Outside Core

Business plugins often need different owners, release cycles, credentials, and
tests.

Keeping them outside core avoids mixing:

- runtime changes
- cloud provider logic
- team-specific APIs
- account or tenant rules
- large test fixtures for external systems

## Core Contract

External plugin repositories should depend on the core contract:

```python
def create_router(context: PluginContext) -> APIRouter:
    ...
```

Plugin selection routes should return:

```json
[
  {"label": "Display text", "value": "stable-value"}
]
```

The plugin repository owns its own resource rules.

## Secrets

Plugin repositories should not ask operators to put secrets in Aperture config.

Use this pattern:

- non-secret plugin settings go in `settings.yaml`
- secrets go in the platform secret manager
- Kubernetes injects secrets as environment variables
- plugin config stores the environment variable name

Example:

```yaml
plugins:
  gitlab:
    enabled: true
    module: aperture_plugin_gitlab.main
    prefix: /gitlab
    config:
      gitlab_url: https://gitlab.example.com
      token_env_var: GITLAB_PAT
```

The plugin repository owns how it validates and uses `GITLAB_PAT`.
