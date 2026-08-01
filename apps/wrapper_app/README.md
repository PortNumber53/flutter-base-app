# Flutter Base App

The mobile wrapper app lives in this directory. Its startup sequence loads
local environment configuration, initializes Supabase, and then renders the
router-based Material app.

## Local setup

Create the ignored runtime configuration file from the committed template:

```sh
cp .env.example .env
```

Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in `.env`. The legacy
`SUPABASE_ANON_KEY` name is also accepted. Only client-safe publishable/anon
keys belong in a Flutter app; never add a Supabase secret or service-role key.

Then fetch packages and run the app:

```sh
flutter pub get
flutter run
```

The `.env` file is bundled as a Flutter asset, so restart the app after changing
it. If the file is absent or invalid, startup renders a safe configuration error
screen instead of exposing the underlying exception.

## Verification

```sh
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
```
