/// Pure domain models for the roadmap feature.

library;

enum TopicStatus { pending, active, done }

TopicStatus _statusFromJson(Object? value) {
  if (value is! String) {
    throw ArgumentError.value(value, 'status', 'Expected a string');
  }
  return TopicStatus.values.byName(value);
}

class RoadmapTopic {
  const RoadmapTopic({
    required this.id,
    required this.title,
    required this.orderIndex,
    required this.prerequisiteIds,
    required this.status,
  });

  factory RoadmapTopic.fromJson(Map<Object?, Object?> json) => RoadmapTopic(
        id: json['id'] as int,
        title: json['title'] as String,
        orderIndex: json['order_index'] as int,
        prerequisiteIds: ((json['prerequisite_ids'] as List<Object?>?) ?? const [])
            .cast<int>(),
        status: _statusFromJson(json['status']),
      );

  final int id;
  final String title;
  final int orderIndex;
  final List<int> prerequisiteIds;
  final TopicStatus status;

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'title': title,
        'order_index': orderIndex,
        'prerequisite_ids': prerequisiteIds,
        'status': status.name,
      };

  @override
  bool operator ==(Object other) =>
      identical(other, this) ||
      other is RoadmapTopic &&
          other.id == id &&
          other.title == title &&
          other.orderIndex == orderIndex &&
          _listEquals(other.prerequisiteIds, prerequisiteIds) &&
          other.status == status;

  @override
  int get hashCode => Object.hash(id, title, orderIndex, prerequisiteIds, status);
}

class Roadmap {
  const Roadmap({
    required this.subjectId,
    required this.topics,
    required this.activeTopicId,
  });

  factory Roadmap.fromJson(Map<Object?, Object?> json) => Roadmap(
        subjectId: json['subject_id'] as String,
        topics: ((json['topics'] as List<Object?>?) ?? const [])
            .cast<Map<Object?, Object?>>()
            .map(RoadmapTopic.fromJson)
            .toList(growable: false),
        activeTopicId: json['active_topic_id'] as int?,
      );

  final String subjectId;
  final List<RoadmapTopic> topics;
  final int? activeTopicId;

  Map<String, Object?> toJson() => <String, Object?>{
        'subject_id': subjectId,
        'topics': [for (final t in topics) t.toJson()],
        'active_topic_id': activeTopicId,
      };

  @override
  bool operator ==(Object other) =>
      identical(other, this) ||
      other is Roadmap &&
          other.subjectId == subjectId &&
          other.activeTopicId == activeTopicId &&
          _listEquals(other.topics, topics);

  @override
  int get hashCode => Object.hash(subjectId, topics, activeTopicId);
}

bool _listEquals<T>(List<T> a, List<T> b) {
  if (identical(a, b)) return true;
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}
