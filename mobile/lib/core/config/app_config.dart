// Placeholder — enable when adding flavors/env.
// ignore_for_file: unused_element
class AppConfig {
  const AppConfig({required this.baseUrl, required this.env});
  final String baseUrl;
  final String env; // dev | stg | prod
  static const dev = AppConfig(baseUrl: 'https://api.dev.upgrade.local', env: 'dev');
  static const prod = AppConfig(baseUrl: 'https://api.upgrade.com', env: 'prod');
}
