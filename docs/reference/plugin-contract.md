# Plugin Contract

Each plugin exposes a router factory:

```python
from fastapi import APIRouter

from aperture.plugins.loader import PluginContext


def create_router(context: PluginContext) -> APIRouter:
    ...
```

## Plugin Configuration

```yaml
plugins:
  demo:
    enabled: true
    module: demo_plugins.demo_data_gouv
    prefix: /demo
    config:
      ttl_seconds: 300
```

Plugin config can contain nested non-secret settings.

Do not put secrets in plugin config. Store secrets in the platform secret
manager and inject them as environment variables.

Example for a GitLab plugin:

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

The plugin reads the URL from `context.settings` and reads the token from the
environment variable named by `token_env_var`.

```python
from os import environ


gitlab_url = context.settings["gitlab_url"]
token_env_var = context.settings["token_env_var"]
gitlab_pat = environ[token_env_var]
```

## Public Response Model

Selection routes must return `list[SelectItem]`.

```json
[
  {"label": "Display text", "value": "stable-value"}
]
```

## Context

`PluginContext` gives the plugin:

- plugin settings
- plugin prefix
- shared cache store
- logger

## Install A Plugin In The Image

External plugins are Python modules. The runtime image must contain the plugin
code so `module` can be imported at startup.

Build your own image from the published Aperture image:

```dockerfile
FROM ghcr.io/cdelgehier/aperture:0.6.1

COPY aperture_plugin_gitlab /app/aperture_plugin_gitlab
```

Then configure the plugin module:

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

If the plugin has dependencies, install them in the derived image. Keep secrets
outside the image.
