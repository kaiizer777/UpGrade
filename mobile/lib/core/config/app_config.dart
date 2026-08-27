class AppConfig {
  const AppConfig({required this.baseUrl, required this.env});

  final String baseUrl;
  final String env; // dev | stg | prod

  static const dev = AppConfig(baseUrl: 'http://127.0.0.1:8000', env: 'dev');
  static const prod = AppConfig(baseUrl: 'https://api.upgrade.com', env: 'prod');

  // --dart-define wiring for prod web builds.
  // Build command:
  //   flutter build web --dart-define=API_BASE_URL=https://<railway-or-fly-url>
  // Falls back to http://127.0.0.1:8000 for local development.
  static const _apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: String.fromEnvironment('API_BASE', defaultValue: 'http://127.0.0.1:8000'),
  );

  static const current = AppConfig(
    baseUrl: _apiBaseUrl,
    env: _apiBaseUrl == 'http://127.0.0.1:8000' ? 'dev' : 'prod',
  );
}
