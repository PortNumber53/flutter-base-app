import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wrapper_app/app.dart';
import 'package:wrapper_app/bootstrap.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('EnvironmentConfig', () {
    test('reads a publishable key', () {
      final config = EnvironmentConfig.fromEnvironment(const {
        'SUPABASE_URL': 'https://example.supabase.co',
        'SUPABASE_PUBLISHABLE_KEY': 'publishable-key',
      });

      expect(config.supabaseUrl, 'https://example.supabase.co');
      expect(config.supabasePublishableKey, 'publishable-key');
    });

    test('supports the legacy anon key name', () {
      final config = EnvironmentConfig.fromEnvironment(const {
        'SUPABASE_URL': 'http://localhost:54321',
        'SUPABASE_ANON_KEY': 'anon-key',
      });

      expect(config.supabasePublishableKey, 'anon-key');
    });

    test('rejects missing values without including supplied values', () {
      expect(
        () => EnvironmentConfig.fromEnvironment(const {
          'SUPABASE_URL': 'https://private-project.supabase.co',
        }),
        throwsA(
          isA<EnvironmentConfigurationException>().having(
            (error) => error.message,
            'message',
            allOf(
              contains('SUPABASE_PUBLISHABLE_KEY'),
              isNot(contains('private-project')),
            ),
          ),
        ),
      );
    });

    test('rejects a non-HTTP URL', () {
      expect(
        () => EnvironmentConfig.fromEnvironment(const {
          'SUPABASE_URL': 'not-a-url',
          'SUPABASE_PUBLISHABLE_KEY': 'publishable-key',
        }),
        throwsA(isA<EnvironmentConfigurationException>()),
      );
    });
  });

  group('bootstrap', () {
    test('initializes the backend before running the app', () async {
      final events = <String>[];
      Widget? renderedApp;

      await bootstrap(
        loadEnvironment: (fileName) async {
          events.add('load:$fileName');
          return const {
            'SUPABASE_URL': 'https://example.supabase.co',
            'SUPABASE_PUBLISHABLE_KEY': 'publishable-key',
          };
        },
        initializeBackend: (config) async {
          events.add('initialize:${config.supabaseUrl}');
        },
        run: (app) {
          events.add('run');
          renderedApp = app;
        },
        reportError: (_, _) => fail('No startup error was expected.'),
        installErrorHandlers: false,
      );

      expect(events, [
        'load:.env',
        'initialize:https://example.supabase.co',
        'run',
      ]);
      expect(renderedApp, isA<App>());
    });

    test('renders a safe failure app when initialization fails', () async {
      final reportedErrors = <Object>[];
      Widget? renderedApp;

      await bootstrap(
        loadEnvironment: (_) async => throw StateError('sensitive-value'),
        run: (app) => renderedApp = app,
        reportError: (error, _) => reportedErrors.add(error),
        installErrorHandlers: false,
      );

      expect(reportedErrors.single, isA<StateError>());
      expect(renderedApp, isA<StartupFailureApp>());
      expect(renderedApp.toString(), isNot(contains('sensitive-value')));
    });
  });

  testWidgets('startup failure screen does not expose exception details', (
    tester,
  ) async {
    await tester.pumpWidget(const StartupFailureApp());

    expect(find.text('Unable to start the app'), findsOneWidget);
    expect(
      find.text('Check the app configuration and try again.'),
      findsOneWidget,
    );
  });
}
