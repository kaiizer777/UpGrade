import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:upgrade/features/onboarding/data/api_client.dart';
import 'package:upgrade/features/onboarding/presentation/providers.dart';
import 'package:upgrade/features/onboarding/presentation/screens/onboarding_screen.dart';

import 'helpers/fake_api_client.dart';

Future<void> pumpScreen(
  WidgetTester tester,
  FakeOnboardingApiClient api, {
  List<String> navigations = const [],
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiProvider.overrideWithValue(api),
        navigateProvider.overrideWithValue((_) {}),
        readyNavigationDelayProvider.overrideWithValue(Duration.zero),
      ],
      child: const MaterialApp(home: OnboardingScreen(subjectId: subjectId)),
    ),
  );
  // Let the seed future resolve and the next frame render it.
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('renders seeded bubbles, progress bar and captions',
      (tester) async {
    final api = FakeOnboardingApiClient(
      initialState: makeState(
        answers: [
          answer('What do you want to learn?', 'Rust', minutes: 1),
          answer('What is your goal?', 'Build a CLI tool', minutes: 3),
        ],
        questionsAsked: 2,
        score: 40,
      ),
    );

    await pumpScreen(tester, api);

    expect(find.byKey(const Key('onboarding-list')), findsOneWidget);
    expect(find.text('What do you want to learn?'), findsOneWidget);
    expect(find.text('Rust'), findsOneWidget);
    expect(find.text('What is your goal?'), findsOneWidget);
    expect(find.text('Build a CLI tool'), findsOneWidget);

    final progressBar = tester.widget<LinearProgressIndicator>(
      find.byKey(const Key('onboarding-progress-bar')),
    );
    expect(progressBar.value, closeTo(0.4, 0.001));
    expect(find.text('Q 2/10'), findsOneWidget);
    expect(find.text('40% complete'), findsOneWidget);
    expect(find.byKey(const Key('typing-indicator')), findsNothing);

    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('send button stays disabled while loading, typing indicator shows, '
      'then reply replaces it', (tester) async {
    final api = FakeOnboardingApiClient(turns: [
      makeTurn(reply: 'Nice. What is your background?', score: 60),
    ]);
    api.gateNextSend(); // hold the API open so we can observe the loading UI

    await pumpScreen(tester, api);

    // Type an answer.
    await tester.enterText(
        find.byKey(const Key('onboarding-input')), 'Self-taught dev');
    await tester.pump();

    IconButton sendButton() => tester.widget<IconButton>(
          find.byKey(const Key('onboarding-send')),
        );
    expect(sendButton().onPressed, isNotNull);

    await tester.tap(find.byKey(const Key('onboarding-send')));
    await tester.pump();

    // While waiting on the API:
    expect(sendButton().onPressed, isNull); // disabled while isLoading
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('onboarding-input')))
          .enabled,
      isFalse,
    );
    expect(find.byKey(const Key('typing-indicator')), findsOneWidget);
    expect(find.text('Nice. What is your background?'), findsNothing);

    // Complete the request.
    await api.releaseNextSend();
    await tester.pumpAndSettle();

    expect(find.text('Nice. What is your background?'), findsOneWidget);
    expect(find.byKey(const Key('typing-indicator')), findsNothing);
    expect(sendButton().onPressed, isNull); // empty input again
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('onboarding-input')))
          .enabled,
      isTrue,
    );
    expect(api.sentMessages, ['Self-taught dev']);

    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('failed send renders a retryable error bubble; retry succeeds',
      (tester) async {
    final api = FakeOnboardingApiClient(
      turns: [makeTurn(reply: 'Got it!', score: 20)],
      sendError: ApiException.network('Could not reach the server'),
    );

    await pumpScreen(tester, api);

    await tester.enterText(
        find.byKey(const Key('onboarding-input')), 'hello there');
    await tester.pump();
    await tester.tap(find.byKey(const Key('onboarding-send')));
    await tester.pumpAndSettle();

    expect(find.text('Message not sent'), findsOneWidget);
    final retryButton = find.widgetWithText(TextButton, 'Retry');
    expect(retryButton, findsOneWidget);
    expect(find.byKey(const Key('typing-indicator')), findsNothing);

    // Second attempt succeeds.
    await tester.tap(retryButton);
    await tester.pumpAndSettle();

    expect(find.text('Message not sent'), findsNothing);
    expect(find.text('Got it!'), findsOneWidget);
    expect(api.sentMessages, ['hello there', 'hello there']);

    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('empty input keeps the send button disabled', (tester) async {
    final api = FakeOnboardingApiClient(initialState: makeState());

    await pumpScreen(tester, api);

    final sendButton = tester.widget<IconButton>(
      find.byKey(const Key('onboarding-send')),
    );
    expect(sendButton.onPressed, isNull);

    // Whitespace-only input still counts as empty.
    await tester.enterText(find.byKey(const Key('onboarding-input')), '   ');
    await tester.pump();
    expect(
      tester
          .widget<IconButton>(find.byKey(const Key('onboarding-send')))
          .onPressed,
      isNull,
    );

    await tester.pumpWidget(const SizedBox());
  });
}
