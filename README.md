# Aperture

![Python](https://img.shields.io/badge/Python-3.14-3776AB.svg?style=for-the-badge&logo=Python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?style=for-the-badge&logo=FastAPI&logoColor=white)
![Task](https://img.shields.io/badge/Task-29BEB0.svg?style=for-the-badge&logo=Task&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-D7FF64.svg?style=for-the-badge&logo=Ruff&logoColor=black)
![ty](https://img.shields.io/badge/ty-261230.svg?style=for-the-badge&logo=Python&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9.svg?style=for-the-badge&logo=uv&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063.svg?style=for-the-badge&logo=Pydantic&logoColor=white)

Aperture is an internal REST API for dynamic select widgets.

It gives platform forms live choices like VPCs, subnets, instance types, snapshots,
and other cloud resources. The public select contract is always:

```json
[
  {"label": "my-vpc-name - vpc-0abc123", "value": "vpc-0abc123"}
]
```

## Quick Start

```bash
uv sync --all-groups
task up
```

Docker Compose guide: [docs/getting-started/demo/README.md](docs/getting-started/demo/README.md).

Useful checks:

```bash
task lint
task type:check
task fmt:check
task test
```

## API Shape

Technical probes stay outside the select contract:

```text
GET /livez
GET /readyz
```

Select and admin routes live under:

```text
/api/v1
```

Current admin routes:

```text
GET /api/v1/admin/plugins
GET /api/v1/admin/routes
GET /api/v1/admin/settings
```

## Runtime Flow

```mermaid
sequenceDiagram
    participant Widget as IDP widget
    participant API as Aperture API
    participant Plugin as Plugin router
    participant Cloud as Cloud API

    Widget->>API: GET /api/v1/{plugin}/{resource}
    API->>Plugin: Route request
    Plugin->>Cloud: Fetch live resources
    Cloud-->>Plugin: Resource list
    Plugin-->>API: list[SelectItem]
    API-->>Widget: [{label, value}]
```

## Application Startup

```mermaid
flowchart TD
    A["create_app(settings)"] --> B["Configure logging"]
    B --> C["Start FastAPI lifespan"]
    C --> D["Load configured plugins"]
    D --> E{"Plugin loaded?"}
    E -->|yes| F["Mount router under /api/v1"]
    E -->|no| G["Store load error"]
    F --> H["readyz returns ready"]
    G --> I["readyz returns not_ready"]
```

## Plugin Contract

Each plugin is a Python module with a router factory:

```python
def create_router(context: PluginContext) -> APIRouter:
    ...
```

```mermaid
classDiagram
    direction LR

    class PluginConfig {
        bool enabled
        str? module
        str prefix
        dict config
    }

    class PluginContext {
        dict settings
        str prefix
    }

    class LoadedPlugin {
        str name
        str prefix
        APIRouter router
    }

    PluginConfig --> PluginContext
    PluginContext --> LoadedPlugin
```

## Configuration

Aperture reads `settings.yml` or `settings.yaml`, then `APT_*` environment
variables can override those values.

Example:

```yaml
port: 8000
log_level: info
cache_backend: memory

plugins:
  admin:
    enabled: true
    module: aperture.plugins.admin.main
    prefix: /admin
    config: {}
```

Environment override example:

```bash
APT_PORT=9000 task up
```

## Logging

Logging uses `structlog`.

```mermaid
flowchart LR
    A[stderr is TTY] -->|yes| B[ConsoleRenderer]
    A -->|no| C[JSONRenderer]
```

Local runs get readable console logs. Containers get JSON logs for log
collectors.

## Cache Contract

Aperture gives plugins one shared async cache store. The default backend is
memory. Redis can be enabled with settings.

```mermaid
flowchart TD
    A["Plugin route"] --> B{"nocache?"}
    B -->|true| E["Fetch live data"]
    B -->|false| C["Read cache"]
    C --> D{"Cache hit?"}
    D -->|yes| G["Return cached SelectItems"]
    D -->|no| E
    E --> F["Write cache with TTL"]
    F --> H["Return fresh SelectItems"]
```

Cache keys use this shape:

```text
plugin:{plugin}:resource:{resource}:scope:{scope...}:params:{hash(params)}
```

The plugin name is always part of the key. Scope segments are chosen by the
plugin, so a cloud plugin can include account and region while a GitLab plugin
can include a group or namespace. Aperture does not use legacy Compass Redis
keys by default.

Plugins choose the TTL that fits each resource. Query parameters that only
change display, like empty options or filtering, should stay out of cache keys.
Synthetic empty select options should be added after cache reads and never
stored in cache.

## Test Rules

- Tests use `pytest`.
- Test files do not use classes.
- JSON examples stay inline in tests.
- Plugin-specific tests live next to the plugin.
