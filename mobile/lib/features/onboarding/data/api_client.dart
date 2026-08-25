import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/models.dart';

/// Typed failure for every non-happy path of [OnboardingApiClient].
///
/// - Non-2xx responses carry the HTTP status plus a message parsed from
///   `{"detail": ...}` (or a generic fallback).
/// - Transport-level failures (SocketException, ClientException, timeouts)
///   are wrapped as [ApiException.network].
class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode})
      : isNetwork = statusCode == null;

  const ApiException.network(this.message)
      : statusCode = null,
        isNetwork = true;

  final String message;

  /// HTTP status code, or `null` when the failure happened before a response
  /// arrived (DNS/socket/timeout).
  final int? statusCode;

  final bool isNetwork;

  /// True when the backend rejected an already-finalized onboarding.
  bool get isAlreadyFinalized => statusCode == 409;

  @override
  String toString() => isNetwork
      ? 'ApiException.network: $message'
      : 'ApiException($statusCode): $message';
}

class OnboardingApiClient {
  OnboardingApiClient({required this.baseUrl, http.Client? client})
      : _client = client ?? http.Client();

  static const Duration _timeout = Duration(seconds: 30);

  final String baseUrl;
  final http.Client _client;

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  static const Map<String, String> _jsonHeaders = {
    'content-type': 'application/json',
    'accept': 'application/json',
  };

  Future<Subject> createSubject(String title, {String? description}) async {
    final response = await _run(
      () => _client.post(
        _uri('/subjects'),
        headers: _jsonHeaders,
        body: jsonEncode(<String, Object?>{
          'title': title,
          'description': description,
        }),
      ),
    );
    return Subject.fromJson(decodeJsonObject(response));
  }

  Future<List<Subject>> listSubjects() async {
    final response = await _run(() => _client.get(_uri('/subjects'), headers: _jsonHeaders));
    final decoded = decodeBody(response);
    if (decoded is! List<Object?>) {
      throw ApiException('Expected a list of subjects', statusCode: response.statusCode);
    }
    return [
      for (final item in decoded) Subject.fromJson(item! as Map<Object?, Object?>),
    ];
  }

  Future<OnboardingTurn> sendMessage(String subjectId, String content) async {
    final response = await _run(
      () => _client.post(
        _uri('/subjects/$subjectId/onboarding/messages'),
        headers: _jsonHeaders,
        body: jsonEncode(<String, Object?>{'content': content}),
      ),
    );
    return OnboardingTurn.fromJson(decodeJsonObject(response));
  }

  Future<OnboardingState> getState(String subjectId) async {
    final response =
        await _run(() => _client.get(_uri('/subjects/$subjectId/onboarding/state'), headers: _jsonHeaders));
    return OnboardingState.fromJson(decodeJsonObject(response));
  }

  void close() => _client.close();

  // ---------------------------------------------------------------------------
  // Internals

  /// Executes [request], mapping transport failures/timeouts to
  /// [ApiException.network] and non-2xx statuses to typed [ApiException]s.
  Future<http.Response> _run(Future<http.Response> Function() request) async {
    http.Response response;
    try {
      // Single deadline covering both connection establishment and receiving
      // the full response — AI generation can legitimately take seconds.
      response = await request().timeout(_timeout);
    } on TimeoutException {
      throw ApiException.network('Request timed out after ${_timeout.inSeconds}s');
    } on Exception catch (error) {
      // SocketException (VM/mobile), http.ClientException (web), etc.
      throw ApiException.network(_transportMessage(error));
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(_detailOf(response), statusCode: response.statusCode);
    }
    return response;
  }

  static String _transportMessage(Object error) =>
      'Could not reach the server (${error.runtimeType}). Check that the API '
      'is running at the configured address.';

  static Object? decodeBody(http.Response response) {
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiException('Malformed JSON in response', statusCode: response.statusCode);
    } on TypeError {
      throw ApiException('Unexpected response encoding', statusCode: response.statusCode);
    }
  }

  static Map<Object?, Object?> decodeJsonObject(http.Response response) {
    final decoded = decodeBody(response);
    if (decoded is Map<Object?, Object?>) return decoded;
    throw ApiException('Expected a JSON object', statusCode: response.statusCode);
  }

  static String _detailOf(http.Response response) {
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is Map && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
    } on Exception {
      // fall through to the generic message
    }
    return 'Request failed with status ${response.statusCode}';
  }
}
