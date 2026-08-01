# Flutter Base App

The mobile wrapper app lives in this directory. Its startup sequence loads
local environment configuration, initializes Supabase, and then renders the
router-based Material app.

## Local setup

Create the ignored build configuration file from the committed template:

```sh
cp .env.example .env
```

Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in `.env`. The legacy
`SUPABASE_ANON_KEY` name is also accepted. Only client-safe publishable/anon
keys belong in a Flutter app; never add a Supabase secret or service-role key.

Then fetch packages and pass the configuration to Flutter as compile-time
defines:

```sh
flutter pub get
flutter run --dart-define-from-file=.env
```

The `.env` file is not bundled as an asset. Release builds must likewise pass
`--dart-define-from-file=.env`; only client-safe values may be compiled into the
app. If the defines are absent or invalid, the build still succeeds and startup
renders a safe configuration error screen instead of exposing the underlying
exception.

## Android release signing

Android release builds are unsigned unless all four signing properties are
provided by the build environment:

- `WRAPPER_RELEASE_STORE_FILE`
- `WRAPPER_RELEASE_STORE_PASSWORD`
- `WRAPPER_RELEASE_KEY_ALIAS`
- `WRAPPER_RELEASE_KEY_PASSWORD`

CI should expose them as Gradle project properties (for example, with the
`ORG_GRADLE_PROJECT_` environment-variable prefix) and then run:

```sh
flutter build appbundle --release --dart-define-from-file=.env
```

Never commit the keystore or its credentials. A partially configured signing
environment fails during Gradle configuration rather than producing an
unexpected artifact.

## Verification

```sh
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
```
