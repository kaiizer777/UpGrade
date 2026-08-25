import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config.dart';
import '../data/api_client.dart';
import '../domain/models.dart';

final roadmapApiProvider = Provider<RoadmapApiClient>((ref) {
  final client = RoadmapApiClient(baseUrl: AppConfig.current.baseUrl);
  ref.onDispose(client.close);
  return client;
});

final roadmapProvider = FutureProvider.family<Roadmap, String>(
  (ref, subjectId) => ref.watch(roadmapApiProvider).getRoadmap(subjectId),
);
