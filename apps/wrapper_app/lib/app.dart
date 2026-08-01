import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:wrapper_app/router.dart';
import 'package:wrapper_app/theme.dart';

class App extends StatelessWidget {
  const App({super.key, this.router});

  final GoRouter? router;

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Flutter Base App',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: router ?? appRouter,
    );
  }
}
