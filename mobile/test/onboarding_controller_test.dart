import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:upgrade/features/onboarding/data/api_client.dart';
import 'package:upgrade/features/onboarding/domain/models.dart';
import 'package:upgrade/features/onboarding/presentation/providers.dart';

import 'helpers/fake_api_client.dart';

void main() {
  ProviderContainer containerOf(
    FakeOnboardingApiClient api, {
    required List<String> navigations,
  }) {
    final container = ProviderContainer(
      overrides: [
        apiProvider.overrideWithValue(api),
        navigateProvider.overrideWithValue((location) => navigations.add(location)),
        readyNavigationDelayProvider.overrideWithValue(Duration.zero),
      ],
      // Riverpod 3 retries failed builds with backoff by default; disable so
      // error-path tests resolve immediately.
      retry: (_, _) => null,
    );
    addTearDown(container.dispose);
    return container;
  }

  OnboardingViewState viewOf(ProviderContainer container) =>
      container.read(onboardingControllerProvider(subjectId)).requireValue;

  group('OnboardingController', () {
    test('seeds transcript from persisted answers (question then reply)',
        () async {
      final api = FakeOnboardingApiClient(
        initialState: makeState(
          answers: [
            answer('What do you want to learn?', 'DSA', minutes: 1),
            answer('What is your goal?', 'FAANG in 3 months', minutes: 5),
          ],
          questionsAsked: 2,
          score: 20,
        ),
      );
      final container = containerOf(api, navigations: []);

      final view = await container.read(onboardingControllerProvider(subjectId).future);

      expect(view.entries, hasLength(4));
      expect(view.entries[0].role, ChatRole.assistant);
      expect(view.entries[0].text, 'What do you want to learn?');
      expect(view.entries[1].role, ChatRole.user);
      expect(view.entries[1].text, 'DSA');
      expect(view.entries[2].text, 'What is your goal?');
      expect(view.entries[3].text, 'FAANG in 3 months');
      expect(view.questionsAsked, 2);
      expect(view.maxQuestions, 10);
      expect(view.completeness!.score, 20);
      expect(view.status, OnboardingStatus.onboarding);
      expect(view.isLoading, isFalse);
    });

    test('successful send appends user bubble + assistant reply and updates progress',
        () async {
      final api = FakeOnboardingApiClient(turns: [
        makeTurn(reply: 'How many hours per week?', score: 40, questionsAsked: 2),
      ]);
      final container = containerOf(api, navigations: []);

      await container.read(onboardingControllerProvider(subjectId).future);
      await container
          .read(onboardingControllerProvider(subjectId).notifier)
          .send('About 10 hours');

      final view = viewOf(container);
      expect(api.sentMessages, ['About 10 hours']);
      expect(view.entries, hasLength(2));
      expect(view.entries[0].role, ChatRole.user);
      expect(view.entries[0].text, 'About 10 hours');
      expect(view.entries.last.role, ChatRole.assistant);
      expect(view.entries.last.text, 'How many hours per week?');
      expect(view.isLoading, isFalse);
      // No lingering typing indicator:
      expect(view.entries.where((e) => e.isTyping), isEmpty);
      expect(view.completeness!.score, 40);
      expect(view.questionsAsked, 2);
    });

    test('error path adds a retryable bubble and keeps the failed message',
        () async {
      final api = FakeOnboardingApiClient(
        sendError: ApiException.network('Could not reach the server'),
      );
      final container = containerOf(api, navigations: []);

      await container.read(onboardingControllerProvider(subjectId).future);
      await container
          .read(onboardingControllerProvider(subjectId).notifier)
          .send('I know arrays');

      final view = viewOf(container);
      expect(view.isLoading, isFalse);
      expect(view.entries.where((e) => e.isTyping), isEmpty);

      final errorEntry = view.entries.last;
      expect(errorEntry.isError, isTrue);
      expect(errorEntry.failedContent, 'I know arrays');

      // The optimistic user bubble survived:
      expect(view.entries.first.role, ChatRole.user);
      expect(view.entries.first.text, 'I know arrays');

      // Retry drops the error bubble and re-sends the same content.
      api.sendError = null;
      await container
          .read(onboardingControllerProvider(subjectId).notifier)
          .resendFailed(errorEntry.id);

      final afterRetry = viewOf(container);
      expect(afterRetry.entries.where((e) => e.isError), isEmpty);
      expect(api.sentMessages, ['I know arrays', 'I know arrays']);
      expect(afterRetry.entries.last.role, ChatRole.assistant);
    });

    test('ready transition flips status, shows banner and navigates to /ready',
        () async {
      final navigations = <String>[];
      final profile = makeProfile();
      final api = FakeOnboardingApiClient(turns: [
        makeTurn(
          reply: "That's everything I need. Your plan is ready!",
          status: OnboardingStatus.ready,
          score: 100,
          profile: profile,
        ),
      ]);
      final container = containerOf(api, navigations: navigations);

      await container.read(onboardingControllerProvider(subjectId).future);
      expect(navigations, isEmpty);

      await container
          .read(onboardingControllerProvider(subjectId).notifier)
          .send('Chill pace please');
      // Allow the (zero-delay in tests) navigation timer to run.
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);

      final view = viewOf(container);
      expect(view.status, OnboardingStatus.ready);
      expect(view.showReadyBanner, isTrue);
      expect(view.profile, profile);
      expect(navigations, ['/subjects/$subjectId/ready']);
    });

    test('seed failure surfaces as AsyncError with the typed exception',
        () async {
      final api = FakeOnboardingApiClient(
        seedError: const ApiException('Not found', statusCode: 404),
      );
      final container = containerOf(api, navigations: []);

      // Trigger the build.
      container.read(onboardingControllerProvider(subjectId));
      await Future<void>.delayed(Duration.zero);

      final asyncValue = container.read(onboardingControllerProvider(subjectId));
      expect(asyncValue.hasValue, isFalse);
      expect(asyncValue, isA<AsyncError>());
      expect(
        (asyncValue as AsyncError).error,
        isA<ApiException>()
            .having((e) => e.statusCode, 'statusCode', 404)
            .having((e) => e.message, 'message', 'Not found'),
      );
    });
  });
}
