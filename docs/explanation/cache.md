# Cache Design

Aperture gives plugins one shared async cache store.

The cache keeps expensive external lookups out of repeated select requests.

```mermaid
flowchart TD
    A["Plugin route"] --> B{"nocache=true?"}
    B -->|yes| E["Fetch live data"]
    B -->|no| C["Read cache"]
    C --> D{"Hit?"}
    D -->|yes| G["Return cached SelectItems"]
    D -->|no| E
    E --> F["Write cache with TTL"]
    F --> H["Return fresh SelectItems"]
```

Cache keys use this shape:

```text
plugin:{plugin}:resource:{resource}:scope:{scope...}:params:{hash(params)}
```

Scope is plugin-owned. A cloud plugin can use account and region. A GitLab
plugin can use group or namespace.
