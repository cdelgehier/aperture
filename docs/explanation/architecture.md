# Architecture

Aperture is a small FastAPI runtime that loads plugin routers.

```mermaid
flowchart LR
    Widget["Internal widget"] --> API["Aperture API"]
    API --> Plugin["Plugin router"]
    Plugin --> Source["External API or data source"]
    Plugin --> Cache["Shared cache"]
    Plugin --> API
    API --> Widget
```

The core owns:

- app startup and shutdown
- settings
- logging
- auth
- error responses
- cache abstraction
- plugin loading

Plugins own resource-specific routes and external API calls.
