# Automation Prototype

The automation pipeline is derived from the requirements in `PRD.md` (section **20: Build, Flavors, CI/CD**).  
The goal is to provide a repeatable sequence that:

- Formats Dart source.
- Runs `flutter analyze`.
- Executes `flutter test --coverage`.
- Builds Android and iOS artifacts per flavor with Fastlane, naming them with the current git SHA.

## CLI Usage

Dry-run the pipeline for all default flavors (`dev`, `stg`, `prod`):

```bash
python -m automation.cli
```

Restrict to a single flavor and pin the SHA (useful in CI):

```bash
python -m automation.cli --flavors prod --sha "$(git rev-parse --short HEAD)"
```

Trigger command execution (will run the listed commands sequentially):

```bash
python -m automation.cli --execute
```

## Integrating with CI

Run the unit tests for the automation tooling:

```bash
python -m unittest
```

Future CI jobs can import `automation.pipeline` to build custom workflows or run the CLI to orchestrate each stage.
