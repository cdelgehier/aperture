# Configuration Reference

Aperture reads `settings.yml` or `settings.yaml`.

`APT_*` environment variables can override settings file values.

Priority is:

```text
init values > APT_* environment variables > .env > settings.yaml > file secrets > defaults
```

For normal deployments, this means:

```text
APT_* environment variables > settings.yaml > application defaults
```

## Common Settings

```yaml
service_name: aperture
listen_addr: 127.0.0.1
port: 8000
log_level: info
cache_backend: memory
cache_default_ttl_seconds: 300
auth_mode: off
```

## Plugin Settings

```yaml
plugins:
  admin:
    enabled: true
    module: aperture.plugins.admin.main
    prefix: /admin
    config: {}
```

## Environment Overrides

```bash
APT_PORT=9000 task up
```
