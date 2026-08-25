import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:upgrade/features/roadmap/data/api_client.dart';
import 'package:upgrade/features/roadmap/presentation/providers.dart';
import 'package:upgrade/features/roadmap/presentation/screens/roadmap_screen.dart';

import 'helpers/fake_roadmap_client.dart';

Future<void> pumpRoadmap(
  WidgetTester tester,
  FakeRoadmapApiClient api, {
  String subjectId = 'subject-1',
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [roadmapApiProvider.overrideWithValue(api)],
      child: MaterialApp(home: RoadmapScreen(subjectId: subjectId)),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('loading shows spinner', (tester) async {
    final api = FakeRoadmapApiClient(delay: const Duration(milliseconds: 200));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [roadmapApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: RoadmapScreen(subjectId: 'subject-1')),
      ),
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    await tester.pumpAndSettle();
  });

  testWidgets('empty state shows CTA button', (tester) async {
    final api = FakeRoadmapApiClient(
      initialRoadmap: makeRoadmap(subjectId: 'subject-1', topics: const [], activeTopicId: null),
    );
    await pumpRoadmap(tester, api);
    expect(find.byKey(const Key('roadmap-empty')), findsOneWidget);
    expect(find.byKey(const Key('roadmap-generate')), findsOneWidget);
    expect(find.text('Generate your personalized roadmap'), findsOneWidget);
  });

  testWidgets('populated roadmap shows ordered topics with badges and status chips', (tester) async {
    final topics = sampleTopics(count: 3);
    final api = FakeRoadmapApiClient(
      initialRoadmap: makeRoadmap(subjectId: 'subject-1', topics: topics, activeTopicId: topics.first.id),
    );
    await pumpRoadmap(tester, api);

    expect(find.byKey(const Key('roadmap-list')), findsOneWidget);
    expect(find.text('Topic 1'), findsOneWidget);
    expect(find.text('Topic 2'), findsOneWidget);
    expect(find.text('Topic 3'), findsOneWidget);
    // Order badges
    expect(find.text('1'), findsWidgets);
    expect(find.text('2'), findsWidgets);
    // Status chips
    expect(find.byKey(const Key('status-chip-active')), findsOneWidget);
    expect(find.byKey(const Key('status-chip-pending')), findsWidgets);
    // Prerequisite trail
    expect(find.text('No prerequisites'), findsOneWidget);
    expect(find.textContaining('Requires:'), findsWidgets);
    // Active highlight and start learning button
    expect(find.byKey(const Key('start-learning')), findsOneWidget);
  });

  testWidgets('409 error shows onboarding CTA', (tester) async {
    final api = FakeRoadmapApiClient(
      getError: const ApiException('Onboarding not finalized', statusCode: 409),
    );
    await pumpRoadmap(tester, api);
    expect(find.byKey(const Key('roadmap-409-text')), findsOneWidget);
    expect(find.text('Complete onboarding first'), findsWidgets);
    expect(find.byKey(const Key('roadmap-back-to-onboarding')), findsOneWidget);
  });

  testWidgets('generate button triggers API and shows topics', (tester) async {
    final empty = makeRoadmap(subjectId: 'subject-1', topics: const [], activeTopicId: null);
    final generated = makeRoadmap(subjectId: 'subject-1', topics: sampleTopics(count: 6), activeTopicId: 100);
    final api = FakeRoadmapApiClient(
      initialRoadmap: empty,
      generateResult: generated,
    );
    await pumpRoadmap(tester, api);
    expect(find.byKey(const Key('roadmap-generate')), findsOneWidget);

    // After generate, the provider should be invalidated and show new list.
    // Fake updates initialRoadmap to generated for the next fetch.
    api.initialRoadmap = generated;

    await tester.tap(find.byKey(const Key('roadmap-generate')));
    await tester.pumpAndSettle();

    expect(api.generateCalls, 1);
    expect(find.byKey(const Key('roadmap-list')), findsOneWidget);
    expect(find.text('Topic 1'), findsOneWidget);
  });

  testWidgets('start learning shows snackbar', (tester) async {
    final topics = sampleTopics(count: 2);
    final api = FakeRoadmapApiClient(
      initialRoadmap: makeRoadmap(subjectId: 'subject-1', topics: topics, activeTopicId: topics.first.id),
    );
    await pumpRoadmap(tester, api);
    await tester.tap(find.byKey(const Key('start-learning')));
    await tester.pump();
    expect(find.text('Feed coming in Phase 5'), findsOneWidget);
  });
}
