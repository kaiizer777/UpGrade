class AppConfig {
  const AppConfig({required this.baseUrl, required this.env});

  final String baseUrl;
  final String env; // dev | stg | prod

  static const dev = AppConfig(baseUrl: 'http://127.0.0.1:8000', env: 'dev');
  static const prod = AppConfig(baseUrl: 'https://api.upgrade.com', env: 'prod');

  // Env wiring: --dart-define=API_BASE=https://api.example.com flips to prod.
  // Default (no define) falls back to dev baseUrl.
  static const current = AppConfig(
    baseUrl: String.fromEnvironment('API_BASE', defaultValue: 'http://127.0.0.1:8000'),
    env: String.fromEnvironment('API_BASE', defaultValue: 'http://127.0.0.1:8000') == 'http://127.0.0.1:8000' ? 'dev' : 'prod',
  );
}
