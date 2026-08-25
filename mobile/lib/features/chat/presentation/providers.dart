import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config.dart';
import '../data/chat_api_client.dart';
import '../domain/models.dart';

final chatApiProvider = Provider<ChatApiClient>((ref) {
  final client = ChatApiClient(baseUrl: AppConfig.current.baseUrl);
  ref.onDispose(client.close);
  return client;
});

/// Per-topic history provider — scoped to subjectId + topicId.
final chatHistoryProvider = FutureProvider.family<List<ChatMessage>, ({String subjectId, int topicId})>(
  (ref, args) => ref.watch(chatApiProvider).getHistory(args.subjectId, args.topicId),
);
