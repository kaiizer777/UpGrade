import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config.dart';
import '../data/api_client.dart';
import '../domain/models.dart';

final feedApiProvider = Provider<FeedApiClient>((ref) {
  final client = FeedApiClient(baseUrl: AppConfig.current.baseUrl);
  ref.onDispose(client.close);
  return client;
});

final feedProvider = FutureProvider.family<Feed, String>(
  (ref, subjectId) => ref.watch(feedApiProvider).getFeed(subjectId),
);

final feedByTopicProvider = FutureProvider.family<Feed, ({String subjectId, int topicId})>(
  (ref, args) => ref.watch(feedApiProvider).getFeed(args.subjectId, topicId: args.topicId),
);
