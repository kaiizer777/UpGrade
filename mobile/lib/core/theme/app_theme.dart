// Placeholder design tokens — wire into MaterialApp.theme when ready.
import 'package:flutter/material.dart';

abstract class AppTheme {
  static ThemeData get light => ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      );
}
