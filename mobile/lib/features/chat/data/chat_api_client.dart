import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/models.dart';

class ChatApiException implements Exception {
  const ChatApiException(this.message, {this.statusCode}) : isNetwork = statusCode == null;
  const ChatApiException.network(this.message) : statusCode = null, isNetwork = true;
  final String message;
  final int? statusCode;
  final bool isNetwork;
  bool get isNotFound => statusCode == 404;
  bool get isServerError => statusCode == 502 || statusCode == 503;
  @override
  String toString() => isNetwork ? 'ChatApiException.network: $message' : 'ChatApiException($statusCode): $message';
}

class ChatApiClient {
  ChatApiClient({required this.baseUrl, http.Client? client}) : _client = client ?? http.Client();

  static const Duration _timeout = Duration(seconds: 60);
  final String baseUrl;
  final http.Client _client;

  Uri _uri(String path) => Uri.parse('$baseUrl$path');
  static const Map<String, String> _jsonHeaders = {
    'content-type': 'application/json',
    'accept': 'application/json',
  };

  Future<ChatResponse> sendMessage(String subjectId, int topicId, String message) async {
    final body = jsonEncode({'message': message});
    final response = await _run(() => _client.post(
          _uri('/subjects/$subjectId/topics/$topicId/chat'),
          headers: _jsonHeaders,
          body: body,
        ));
    return ChatResponse.fromJson(_decodeJsonObject(response));
  }

  Future<List<ChatMessage>> getHistory(String subjectId, int topicId) async {
    final response = await _run(() => _client.get(
          _uri('/subjects/$subjectId/topics/$topicId/chat'),
          headers: _jsonHeaders,
        ));
    final decoded = _decodeJsonObject(response);
    final list = decoded['messages'] as List<Object?>? ?? const [];
    return list.cast<Map<Object?, Object?>>().map(ChatMessage.fromJson).toList(growable: false);
  }

  void close() => _client.close();

  Future<http.Response> _run(Future<http.Response> Function() request) async {
    http.Response response;
    try {
      response = await request().timeout(_timeout);
    } on TimeoutException {
      throw ChatApiException.network('Request timed out after ${_timeout.inSeconds}s');
    } on Exception catch (e) {
      throw ChatApiException.network('Could not reach server (${e.runtimeType}). Check API at $baseUrl');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ChatApiException(_detailOf(response), statusCode: response.statusCode);
    }
    return response;
  }

  static Object? _decodeBody(http.Response response) {
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ChatApiException('Malformed JSON', statusCode: response.statusCode);
    }
  }

  static Map<Object?, Object?> _decodeJsonObject(http.Response response) {
    final decoded = _decodeBody(response);
    if (decoded is Map<Object?, Object?>) return decoded;
    throw ChatApiException('Expected JSON object', statusCode: response.statusCode);
  }

  static String _detailOf(http.Response response) {
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is Map && decoded['detail'] is String) return decoded['detail'] as String;
    } catch (_) {}
    return 'Request failed ${response.statusCode}';
  }
}
