import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:upgrade/features/feed/data/api_client.dart';
import 'package:upgrade/features/feed/domain/models.dart';
import 'package:upgrade/features/feed/presentation/providers.dart';
import 'package:upgrade/features/feed/presentation/screens/feed_screen.dart';
import 'package:upgrade/features/onboarding/domain/models.dart' as onboarding;
import 'package:upgrade/features/onboarding/presentation/providers.dart';

class FakeFeedApiClient implements FeedApiClient {
  FakeFeedApiClient({
    this.feed,
    this.getError,
  });

  Feed? feed;
  Object? getError;
  int getCalls = 0;
  int prefetchCalls = 0;
  int completeCalls = 0;

  @override
  String get baseUrl => 'fake://api';

  @override
  Future<Feed> getFeed(String subjectId, {int? topicId}) async {
    getCalls++;
    if (getError != null) throw getError!;
    return feed ??
        const Feed(
          subjectId: 'subject-1',
          topic: FeedTopic(
            id: 1,
            title: 'Introduction to Algorithms',
            orderIndex: 1,
            status: 'active',
            prerequisiteIds: [],
          ),
          topicId: 1,
          posts: [
            FeedPost(
              id: 1,
              topicId: 1,
              content: 'Lesson 1: What is Big-O notation?',
              orderIndex: 0,
              createdAt: '2026-08-26T00:00:00Z',
            ),
          ],
          postCount: 1,
        );
  }

  @override
  Future<Map<Object?, Object?>> prefetch(String subjectId, int topicId) async {
    prefetchCalls++;
    return {'status': 'prefetch_triggered'};
  }

  @override
  Future<CompleteResult> completeTopic(int topicId) async {
    completeCalls++;
    return const CompleteResult(
      completedTopicId: 1,
      status: 'done',
      deletedCount: 1,
      nextTopicId: 2,
      nextTopicTitle: 'Recursion',
      allCompleted: false,
    );
  }

  @override
  void close() {}
}

class FakeSubjectsNotifier extends SubjectsNotifier {
  @override
  Future<List<onboarding.Subject>> build() async => const [];
}

Future<void> pumpFeedScreen(
  WidgetTester tester, {
  FeedApiClient? api,
  AsyncValue<Feed>? feedOverride,
  String subjectId = 'subject-1',
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        subjectsProvider.overrideWith(FakeSubjectsNotifier.new),
        if (api != null) feedApiProvider.overrideWithValue(api),
        if (feedOverride != null)
          feedProvider(subjectId).overrideWith((ref) => feedOverride.value!),
      ],
      child: MaterialApp(
        home: FeedScreen(subjectId: subjectId),
      ),
    ),
  );
}

void main() {
  testWidgets('loading shows spinner and caption text', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          subjectsProvider.overrideWith(FakeSubjectsNotifier.new),
          feedProvider('subject-1').overrideWith((ref) async {
            await Future<void>.delayed(const Duration(milliseconds: 500));
            return const Feed(
              subjectId: 'subject-1',
              topic: null,
              topicId: null,
              posts: [],
              postCount: 0,
            );
          }),
        ],
        child: const MaterialApp(
          home: FeedScreen(subjectId: 'subject-1'),
        ),
      ),
    );

    expect(find.byKey(const Key('feed-loading-indicator')), findsOneWidget);
    expect(find.byKey(const Key('feed-loading-text')), findsOneWidget);
    expect(find.text('Generating your next feed...'), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 600));
  });

  testWidgets('error state 502 / generation failure shows retry and message', (tester) async {
    final api = FakeFeedApiClient(
      getError: const FeedApiException('Feed generation failed: Groq timeout', statusCode: 502),
    );
    await pumpFeedScreen(tester, api: api);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('feed-error-text')), findsOneWidget);
    expect(find.textContaining('Feed generation failed'), findsOneWidget);
    expect(find.byKey(const Key('feed-retry')), findsOneWidget);

    // Tap retry
    api.getError = null;
    await tester.tap(find.byKey(const Key('feed-retry')));
    await tester.pumpAndSettle();
    expect(api.getCalls, greaterThanOrEqualTo(2));
  });

  testWidgets('error state 503 / Redis down / network error shows retry', (tester) async {
    final api = FakeFeedApiClient(
      getError: const FeedApiException('AI provider not configured', statusCode: 503),
    );
    await pumpFeedScreen(tester, api: api);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('feed-error-text')), findsOneWidget);
    expect(find.textContaining('Service temporarily unavailable'), findsOneWidget);
    expect(find.byKey(const Key('feed-retry')), findsOneWidget);
  });

  testWidgets('error state 409 / 404 shows retry and roadmap guidance', (tester) async {
    final api = FakeFeedApiClient(
      getError: const FeedApiException('No active topic found', statusCode: 409),
    );
    await pumpFeedScreen(tester, api: api);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('feed-error-text')), findsOneWidget);
    expect(find.text('No active topic found'), findsOneWidget);
    expect(find.byKey(const Key('feed-retry')), findsOneWidget);
  });

  testWidgets('empty feed data state shows generation message and retry', (tester) async {
    final api = FakeFeedApiClient(
      feed: const Feed(
        subjectId: 'subject-1',
        topic: FeedTopic(
          id: 1,
          title: 'Topic 1',
          orderIndex: 1,
          status: 'active',
          prerequisiteIds: [],
        ),
        topicId: 1,
        posts: [],
        postCount: 0,
      ),
    );
    await pumpFeedScreen(tester, api: api);
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byKey(const Key('feed-empty')), findsOneWidget);
    expect(find.text('Generating your personalized feed...'), findsOneWidget);
    expect(find.byKey(const Key('feed-empty-retry')), findsOneWidget);
  });

  testWidgets('no active topic data state shows no topic UI and retry', (tester) async {
    final api = FakeFeedApiClient(
      feed: const Feed(
        subjectId: 'subject-1',
        topic: null,
        topicId: null,
        posts: [],
        postCount: 0,
        allTopicsCompleted: false,
      ),
    );
    await pumpFeedScreen(tester, api: api);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('feed-no-topic')), findsOneWidget);
    expect(find.text('No active topic yet'), findsOneWidget);
    expect(find.byKey(const Key('feed-no-topic-retry')), findsOneWidget);
    expect(find.byKey(const Key('feed-no-topic-roadmap')), findsOneWidget);
  });

  testWidgets('populated feed renders topic header and posts', (tester) async {
    final api = FakeFeedApiClient();
    await pumpFeedScreen(tester, api: api);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('feed-topic-header')), findsOneWidget);
    expect(find.text('Introduction to Algorithms'), findsOneWidget);
    expect(find.byKey(const ValueKey('post-1')), findsOneWidget);
    expect(find.text('Lesson 1: What is Big-O notation?'), findsOneWidget);
    expect(find.byKey(const Key('complete-topic')), findsOneWidget);
  });
}
