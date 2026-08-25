import 'package:flutter_test/flutter_test.dart';
import 'package:upgrade/features/roadmap/domain/models.dart';

void main() {
  group('RoadmapTopic', () {
    test('parses and round-trips', () {
      const json = <String, Object?>{
        'id': 42,
        'title': 'Arrays & Hashing',
        'order_index': 1,
        'prerequisite_ids': <int>[],
        'status': 'active',
      };
      final topic = RoadmapTopic.fromJson(json);
      expect(topic.id, 42);
      expect(topic.title, 'Arrays & Hashing');
      expect(topic.orderIndex, 1);
      expect(topic.prerequisiteIds, isEmpty);
      expect(topic.status, TopicStatus.active);
      expect(topic.toJson(), json);
      expect(RoadmapTopic.fromJson(topic.toJson()), topic);
    });

    test('parses prerequisite ids and pending status', () {
      const json = <String, Object?>{
        'id': 3,
        'title': 'Stack & Queue',
        'order_index': 3,
        'prerequisite_ids': [1, 2],
        'status': 'pending',
      };
      final topic = RoadmapTopic.fromJson(json);
      expect(topic.prerequisiteIds, [1, 2]);
      expect(topic.status, TopicStatus.pending);
    });

    test('rejects unknown status', () {
      expect(
        () => RoadmapTopic.fromJson(const <String, Object?>{
          'id': 1,
          'title': 'X',
          'order_index': 1,
          'prerequisite_ids': [],
          'status': 'unknown',
        }),
        throwsArgumentError,
      );
    });
  });

  group('Roadmap', () {
    test('parses empty roadmap', () {
      const json = <String, Object?>{
        'subject_id': 's-1',
        'topics': <Object?>[],
        'active_topic_id': null,
      };
      final roadmap = Roadmap.fromJson(json);
      expect(roadmap.subjectId, 's-1');
      expect(roadmap.topics, isEmpty);
      expect(roadmap.activeTopicId, isNull);
      expect(roadmap.toJson(), json);
    });

    test('parses populated roadmap ordered', () {
      const json = <String, Object?>{
        'subject_id': 's-9',
        'topics': [
          {
            'id': 10,
            'title': 'Arrays & Hashing',
            'order_index': 1,
            'prerequisite_ids': [],
            'status': 'active',
          },
          {
            'id': 11,
            'title': 'Two Pointers',
            'order_index': 2,
            'prerequisite_ids': [10],
            'status': 'pending',
          },
        ],
        'active_topic_id': 10,
      };
      final roadmap = Roadmap.fromJson(json);
      expect(roadmap.topics, hasLength(2));
      expect(roadmap.topics[0].orderIndex, 1);
      expect(roadmap.topics[1].prerequisiteIds, [10]);
      expect(roadmap.activeTopicId, 10);
      expect(Roadmap.fromJson(roadmap.toJson()), roadmap);
    });

    test('round-trips with done status', () {
      final roadmap = Roadmap(
        subjectId: 's-x',
        topics: const [
          RoadmapTopic(
            id: 1,
            title: 'Intro',
            orderIndex: 1,
            prerequisiteIds: [],
            status: TopicStatus.done,
          ),
        ],
        activeTopicId: null,
      );
      expect(Roadmap.fromJson(roadmap.toJson()), roadmap);
    });
  });
}
