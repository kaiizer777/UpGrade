library;

class FeedTopic {
  const FeedTopic({
    required this.id,
    required this.title,
    required this.orderIndex,
    required this.status,
    required this.prerequisiteIds,
  });

  factory FeedTopic.fromJson(Map<Object?, Object?> json) => FeedTopic(
        id: json['id'] as int,
        title: json['title'] as String,
        orderIndex: json['order_index'] as int,
        status: json['status'] as String,
        prerequisiteIds: ((json['prerequisite_ids'] as List<Object?>?) ?? const [])
            .cast<int>(),
      );

  final int id;
  final String title;
  final int orderIndex;
  final String status;
  final List<int> prerequisiteIds;
}

class FeedPost {
  const FeedPost({
    required this.id,
    required this.topicId,
    required this.content,
    required this.orderIndex,
    required this.createdAt,
  });

  factory FeedPost.fromJson(Map<Object?, Object?> json) => FeedPost(
        id: json['id'] as int,
        topicId: json['topic_id'] as int,
        content: json['content'] as String,
        orderIndex: json['order_index'] as int,
        createdAt: json['created_at'] as String?,
      );

  final int id;
  final int topicId;
  final String content;
  final int orderIndex;
  final String? createdAt;
}

class Feed {
  const Feed({
    required this.subjectId,
    required this.topic,
    required this.topicId,
    required this.posts,
    required this.postCount,
    this.allTopicsCompleted = false,
  });

  factory Feed.fromJson(Map<Object?, Object?> json) {
    final topicRaw = json['topic'];
    FeedTopic? topic;
    if (topicRaw is Map<Object?, Object?>) {
      topic = FeedTopic.fromJson(topicRaw);
    }
    final postsRaw = json['posts'] as List<Object?>? ?? const [];
    return Feed(
      subjectId: json['subject_id'] as String? ?? '',
      topic: topic,
      topicId: json['topic_id'] as int?,
      posts: postsRaw
          .cast<Map<Object?, Object?>>()
          .map(FeedPost.fromJson)
          .toList(growable: false),
      postCount: json['post_count'] as int? ?? postsRaw.length,
      allTopicsCompleted: json['all_topics_completed'] as bool? ?? false,
    );
  }

  final String subjectId;
  final FeedTopic? topic;
  final int? topicId;
  final List<FeedPost> posts;
  final int postCount;
  final bool allTopicsCompleted;
}

class CompleteResult {
  const CompleteResult({
    required this.completedTopicId,
    required this.status,
    required this.deletedCount,
    this.nextTopicId,
    this.nextTopicTitle,
    required this.allCompleted,
  });

  factory CompleteResult.fromJson(Map<Object?, Object?> json) => CompleteResult(
        completedTopicId: json['completed_topic_id'] as int,
        status: json['status'] as String? ?? 'done',
        deletedCount: json['deleted_feed_posts_count'] as int? ?? 0,
        nextTopicId: json['next_topic_id'] as int?,
        nextTopicTitle: json['next_topic_title'] as String?,
        allCompleted: json['all_topics_completed'] as bool? ?? false,
      );

  final int completedTopicId;
  final String status;
  final int deletedCount;
  final int? nextTopicId;
  final String? nextTopicTitle;
  final bool allCompleted;
}
