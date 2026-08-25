import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/models.dart';

class FeedApiException implements Exception {
  const FeedApiException(this.message, {this.statusCode}) : isNetwork = statusCode == null;
  const FeedApiException.network(this.message) : statusCode = null, isNetwork = true;
  final String message;
  final int? statusCode;
  final bool isNetwork;
  bool get isNotFound => statusCode == 404;
  bool get isConflict => statusCode == 409;
  bool get isServerError => statusCode == 502 || statusCode == 503;
  @override
  String toString() => isNetwork ? 'FeedApiException.network: $message' : 'FeedApiException($statusCode): $message';
}

class FeedApiClient {
  FeedApiClient({required this.baseUrl, http.Client? client}) : _client = client ?? http.Client();
  static const Duration _timeout = Duration(seconds: 60);
  final String baseUrl;
  final http.Client _client;
  Uri _uri(String path) => Uri.parse('$baseUrl$path');
  static const Map<String, String> _jsonHeaders = {'content-type': 'application/json', 'accept': 'application/json'};

  Future<Feed> getFeed(String subjectId, {int? topicId}) async {
    final query = topicId != null ? '?topic_id=$topicId' : '';
    final response = await _run(() => _client.get(_uri('/subjects/$subjectId/feed$query'), headers: _jsonHeaders));
    return Feed.fromJson(_decodeJsonObject(response));
  }

  Future<Map<Object?, Object?>> prefetch(String subjectId, int topicId) async {
    final response = await _run(() => _client.post(_uri('/subjects/$subjectId/topics/$topicId/prefetch'), headers: _jsonHeaders));
    return _decodeJsonObject(response);
  }

  Future<CompleteResult> completeTopic(int topicId) async {
    final response = await _run(() => _client.post(_uri('/topics/$topicId/complete'), headers: _jsonHeaders));
    return CompleteResult.fromJson(_decodeJsonObject(response));
  }

  void close() => _client.close();

  Future<http.Response> _run(Future<http.Response> Function() request) async {
    http.Response response;
    try {
      response = await request().timeout(_timeout);
    } on TimeoutException {
      throw FeedApiException.network('Request timed out after ${_timeout.inSeconds}s');
    } on Exception catch (e) {
      throw FeedApiException.network('Could not reach server (${e.runtimeType}). Check API at $baseUrl');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw FeedApiException(_detailOf(response), statusCode: response.statusCode);
    }
    return response;
  }

  static Object? _decodeBody(http.Response response) {
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw FeedApiException('Malformed JSON', statusCode: response.statusCode);
    }
  }

  static Map<Object?, Object?> _decodeJsonObject(http.Response response) {
    final decoded = _decodeBody(response);
    if (decoded is Map<Object?, Object?>) return decoded;
    throw FeedApiException('Expected JSON object', statusCode: response.statusCode);
  }

  static String _detailOf(http.Response response) {
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is Map && decoded['detail'] is String) return decoded['detail'] as String;
    } catch (_) {}
    return 'Request failed ${response.statusCode}';
  }
}
