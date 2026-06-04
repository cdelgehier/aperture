# Deploy With Helm

The chart lives in `helm/aperture`.

## Non-Production

```bash
helm upgrade --install aperture ./helm/aperture \
  -f helm/aperture/values-nonprod.yaml
```

## Production

```bash
helm upgrade --install aperture ./helm/aperture \
  -f helm/aperture/values-prod.yaml
```

## Published Chart

Install the published OCI chart:

```bash
helm upgrade --install aperture \
  oci://ghcr.io/cdelgehier/charts/aperture \
  --version 0.5.1
```

List available chart versions with `crane`.
`crane` is a small GoogleContainerTools CLI for reading OCI registries:

```bash
crane ls ghcr.io/cdelgehier/charts/aperture
```

Production should set:

- `auth.mode=api_key`
- `auth.apiKeys.existingSecret`
- `aperture.cacheBackend=redis`
- `redis.url`

## Configuration

The chart uses two ConfigMaps:

- `aperture-env` for simple `APT_*` environment variables.
- `aperture-settings` for `settings.yaml`, mainly plugin config.

Priority is:

```text
APT_* environment variables > settings.yaml > application defaults
```

## Plugin Secrets

Plugin settings can go in `aperture.plugins`.

Secrets must not go in `values.yaml` or `settings.yaml`. Store them in an
existing Kubernetes Secret and inject them with `extraEnv`.

Example for a GitLab plugin:

```yaml
aperture:
  plugins:
    gitlab:
      enabled: true
      module: aperture_plugin_gitlab.main
      prefix: /gitlab
      config:
        gitlab_url: https://gitlab.example.com
        token_env_var: GITLAB_PAT

extraEnv:
  - name: GITLAB_PAT
    valueFrom:
      secretKeyRef:
        name: gitlab-plugin-secret
        key: GITLAB_PAT
```

This keeps the GitLab URL readable in `settings.yaml`, but keeps the PAT in a
Kubernetes Secret.

## Use Your Own Plugin Image

Aperture plugins must be importable by Python at runtime.

Create a derived image:

```dockerfile
FROM ghcr.io/cdelgehier/aperture:0.5.1

COPY aperture_plugin_gitlab /app/aperture_plugin_gitlab
```

Publish it:

```bash
docker build -t ghcr.io/acme/aperture-gitlab:0.1.0 .
docker push ghcr.io/acme/aperture-gitlab:0.1.0
```

Use it with the chart:

```yaml
image:
  repository: ghcr.io/acme/aperture-gitlab
  tag: "0.1.0"

aperture:
  plugins:
    gitlab:
      enabled: true
      module: aperture_plugin_gitlab.main
      prefix: /gitlab
      config:
        gitlab_url: https://gitlab.example.com
        token_env_var: GITLAB_PAT
```

If the plugin needs a PAT or another secret, inject it with `extraEnv` as shown
above.

## Exposure

Use Gateway API when the cluster has a Gateway controller and CRDs installed.
Use Ingress for simpler or older clusters.
