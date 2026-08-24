// Placeholder app composition — not yet wired into main.dart.
// Keeps scaffolding importable without breaking the empty template.
import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'UpGrade',
      theme: AppTheme.light,
      home: const Scaffold(body: Center(child: Text('Hello World!'))),
    );
  }
}
