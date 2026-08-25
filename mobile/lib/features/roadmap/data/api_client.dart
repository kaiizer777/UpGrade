import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/models.dart';

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode}) : isNetwork = statusCode == null;

  const ApiException.network(this.message)
      : statusCode = null,
        isNetwork = true;

  final String message;
  final int? statusCode;
  final bool isNetwork;

  bool get isNotFound => statusCode == 404;
  bool get isOnboardingNotReady => statusCode == 409;
  bool get isServerError => statusCode == 502 || statusCode == 503;

  @override
  String toString() => isNetwork
      ? 'ApiException.network: $message'
      : 'ApiException($statusCode): $message';
}

class RoadmapApiClient {
  RoadmapApiClient({required this.baseUrl, http.Client? client}) : _client = client ?? http.Client();

  static const Duration _timeout = Duration(seconds: 30);

  final String baseUrl;
  final http.Client _client;

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  static const Map<String, String> _jsonHeaders = {
    'content-type': 'application/json',
    'accept': 'application/json',
  };

  Future<Roadmap> getRoadmap(String subjectId) async {
    final response = await _run(() => _client.get(_uri('/subjects/$subjectId/roadmap'), headers: _jsonHeaders));
    return Roadmap.fromJson(_decodeJsonObject(response));
  }

  Future<Roadmap> generateRoadmap(String subjectId) async {
    final response = await _run(() => _client.post(_uri('/subjects/$subjectId/roadmap'), headers: _jsonHeaders));
    return Roadmap.fromJson(_decodeJsonObject(response));
  }

  void close() => _client.close();

  Future<http.Response> _run(Future<http.Response> Function() request) async {
    http.Response response;
    try {
      response = await request().timeout(_timeout);
    } on TimeoutException {
      throw ApiException.network('Request timed out after ${_timeout.inSeconds}s');
    } on Exception catch (error) {
      throw ApiException.network(_transportMessage(error));
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(_detailOf(response), statusCode: response.statusCode);
    }
    return response;
  }

  static String _transportMessage(Object error) =>
      'Could not reach the server (${error.runtimeType}). Check that the API is running at the configured address.';

  static Object? _decodeBody(http.Response response) {
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiException('Malformed JSON in response', statusCode: response.statusCode);
    } on TypeError {
      throw ApiException('Unexpected response encoding', statusCode: response.statusCode);
    }
  }

  static Map<Object?, Object?> _decodeJsonObject(http.Response response) {
    final decoded = _decodeBody(response);
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
      // fall through
    }
    return 'Request failed with status ${response.statusCode}';
  }
}
