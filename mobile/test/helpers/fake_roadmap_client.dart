import 'package:upgrade/features/roadmap/data/api_client.dart';
import 'package:upgrade/features/roadmap/domain/models.dart';

Roadmap makeRoadmap({
  String subjectId = 'subject-1',
  List<RoadmapTopic> topics = const [],
  int? activeTopicId,
}) =>
    Roadmap(subjectId: subjectId, topics: topics, activeTopicId: activeTopicId);

List<RoadmapTopic> sampleTopics({int count = 3}) => List.generate(
      count,
      (i) => RoadmapTopic(
        id: 100 + i,
        title: 'Topic ${i + 1}',
        orderIndex: i + 1,
        prerequisiteIds: i == 0 ? const [] : [100 + i - 1],
        status: i == 0 ? TopicStatus.active : TopicStatus.pending,
      ),
    );

class FakeRoadmapApiClient implements RoadmapApiClient {
  FakeRoadmapApiClient({
    this.initialRoadmap,
    this.generateResult,
    this.getError,
    this.generateError,
    this.delay = Duration.zero,
  });

  Roadmap? initialRoadmap;
  Roadmap? generateResult;
  Object? getError;
  Object? generateError;
  Duration delay;

  int getCalls = 0;
  int generateCalls = 0;

  @override
  String get baseUrl => 'fake://api';

  @override
  Future<Roadmap> getRoadmap(String subjectId) async {
    getCalls++;
    if (delay != Duration.zero) await Future.delayed(delay);
    if (getError != null) throw getError!;
    if (initialRoadmap != null) return initialRoadmap!;
    return makeRoadmap(subjectId: subjectId, topics: const [], activeTopicId: null);
  }

  @override
  Future<Roadmap> generateRoadmap(String subjectId) async {
    generateCalls++;
    if (delay != Duration.zero) await Future.delayed(delay);
    if (generateError != null) throw generateError!;
    if (generateResult != null) return generateResult!;
    final topics = sampleTopics(count: 6);
    return makeRoadmap(subjectId: subjectId, topics: topics, activeTopicId: topics.first.id);
  }

  @override
  void close() {}
}
