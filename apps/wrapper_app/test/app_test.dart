import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wrapper_app/app.dart';
import 'package:wrapper_app/router.dart';

void main() {
  testWidgets('renders the configured router and home route', (tester) async {
    await tester.pumpWidget(const App());
    await tester.pumpAndSettle();

    final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(materialApp.routerConfig, same(appRouter));
    expect(materialApp.theme?.useMaterial3, isTrue);
    expect(materialApp.darkTheme?.brightness, Brightness.dark);
    expect(find.text('Flutter Base App'), findsOneWidget);
    expect(find.text('App initialized successfully'), findsOneWidget);
  });
}
