import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:wrapper_app/app.dart';
import 'package:wrapper_app/theme.dart';

const _defaultEnvironmentFile = '.env';
const _supabaseUrlKey = 'SUPABASE_URL';
const _supabasePublishableKey = 'SUPABASE_PUBLISHABLE_KEY';
const _legacySupabaseAnonKey = 'SUPABASE_ANON_KEY';

typedef EnvironmentLoader =
    Future<Map<String, String>> Function(String fileName);
typedef BackendInitializer = Future<void> Function(EnvironmentConfig config);
typedef AppRunner = void Function(Widget app);
typedef ErrorReporter = void Function(Object error, StackTrace stackTrace);

/// Loads configuration and initializes services before rendering the app.
///
/// Dependencies are injectable so the startup sequence can be verified without
/// connecting tests to Supabase or reading an asset bundle.
Future<void> bootstrap({
  String environmentFile = _defaultEnvironmentFile,
  EnvironmentLoader? loadEnvironment,
  BackendInitializer? initializeBackend,
  AppRunner run = runApp,
  ErrorReporter reportError = _reportError,
  bool installErrorHandlers = true,
}) async {
  WidgetsFlutterBinding.ensureInitialized();

  if (installErrorHandlers) {
    _installGlobalErrorHandlers(reportError);
  }

  try {
    final values = await (loadEnvironment ?? _loadEnvironment)(environmentFile);
    final config = EnvironmentConfig.fromEnvironment(values);

    await (initializeBackend ?? _initializeSupabase)(config);
    run(const App());
  } catch (error, stackTrace) {
    reportError(error, stackTrace);
    run(const StartupFailureApp());
  }
}

Future<Map<String, String>> _loadEnvironment(String fileName) async {
  await dotenv.load(fileName: fileName);
  return Map.unmodifiable(dotenv.env);
}

Future<void> _initializeSupabase(EnvironmentConfig config) async {
  await Supabase.initialize(
    url: config.supabaseUrl,
    publishableKey: config.supabasePublishableKey,
  );
}

void _installGlobalErrorHandlers(ErrorReporter reportError) {
  FlutterError.onError = (details) {
    reportError(details.exception, details.stack ?? StackTrace.current);
  };
  PlatformDispatcher.instance.onError = (error, stackTrace) {
    reportError(error, stackTrace);
    return true;
  };
}

void _reportError(Object error, StackTrace stackTrace) {
  // Deliberately omit the error value: third-party exceptions can contain
  // configuration values that must not appear in logs.
  debugPrint('Application initialization failed (${error.runtimeType}).');
  debugPrintStack(stackTrace: stackTrace);
}

@immutable
class EnvironmentConfig {
  const EnvironmentConfig({
    required this.supabaseUrl,
    required this.supabasePublishableKey,
  });

  factory EnvironmentConfig.fromEnvironment(Map<String, String> values) {
    final url = _nonEmpty(values[_supabaseUrlKey]);
    final publishableKey =
        _nonEmpty(values[_supabasePublishableKey]) ??
        _nonEmpty(values[_legacySupabaseAnonKey]);

    if (url == null || publishableKey == null) {
      final missing = <String>[
        if (url == null) _supabaseUrlKey,
        if (publishableKey == null)
          '$_supabasePublishableKey (or $_legacySupabaseAnonKey)',
      ];
      throw EnvironmentConfigurationException(
        'Missing required environment variable(s): ${missing.join(', ')}.',
      );
    }

    final parsedUrl = Uri.tryParse(url);
    if (parsedUrl == null ||
        !parsedUrl.hasScheme ||
        parsedUrl.host.isEmpty ||
        (parsedUrl.scheme != 'https' && parsedUrl.scheme != 'http')) {
      throw const EnvironmentConfigurationException(
        'SUPABASE_URL must be an absolute HTTP or HTTPS URL.',
      );
    }

    return EnvironmentConfig(
      supabaseUrl: url,
      supabasePublishableKey: publishableKey,
    );
  }

  final String supabaseUrl;
  final String supabasePublishableKey;

  static String? _nonEmpty(String? value) {
    final trimmed = value?.trim();
    return trimmed == null || trimmed.isEmpty ? null : trimmed;
  }
}

class EnvironmentConfigurationException implements Exception {
  const EnvironmentConfigurationException(this.message);

  final String message;

  @override
  String toString() => 'EnvironmentConfigurationException: $message';
}

class StartupFailureApp extends StatelessWidget {
  const StartupFailureApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flutter Base App',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      home: const _StartupFailureScreen(),
    );
  }
}

class _StartupFailureScreen extends StatelessWidget {
  const _StartupFailureScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.error_outline,
                  size: 48,
                  color: Theme.of(context).colorScheme.error,
                ),
                const SizedBox(height: 16),
                Text(
                  'Unable to start the app',
                  style: Theme.of(context).textTheme.headlineSmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Check the app configuration and try again.',
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
