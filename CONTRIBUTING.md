# Contribution guidelines

Contributions are welcome: bug reports, fixes and feature proposals. Use GitHub [issues](../../issues) and pull requests.

The protocol code lives in the [vitafit-ble](https://github.com/jamesmyatt/vitafit-ble) library. Report scale protocol problems there.

## Pull requests

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Make sure the pre-commit hooks pass (`scripts/lint`) and the tests pass (`pytest`). `scripts/setup` installs the hooks.
4. Open the pull request.

## Bug reports

Include:

- What you did, what you expected, and what happened
- Your Home Assistant version, and whether the scale connects through a local adapter or an ESPHome proxy
- Debug logs, enabled with:

  ```yaml
  logger:
    logs:
      custom_components.vitafit_ble: debug
      vitafit_ble: debug
  ```

## Development environment

This repo is based on the [integration_blueprint](https://github.com/ludeeus/integration_blueprint) template. Home Assistant doesn't run on Windows, so use Linux, WSL or the included dev container.

The dev container sets everything up. Elsewhere, with [uv](https://docs.astral.sh/uv/):

```sh
uv venv --python 3.14
. .venv/bin/activate
scripts/setup
```

`scripts/develop` starts Home Assistant with this integration, using [`config/configuration.yaml`](./config/configuration.yaml).

## Licence

By contributing, you agree that your contributions will be licensed under the project's [MIT License](./LICENSE).
