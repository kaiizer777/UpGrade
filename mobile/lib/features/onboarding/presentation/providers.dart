import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router.dart';
import '../../../core/config/app_config.dart';
import '../data/api_client.dart';
import '../domain/models.dart';

/// Single shared API client pointed at [AppConfig.current].
final apiProvider = Provider<OnboardingApiClient>((ref) {
  final client = OnboardingApiClient(baseUrl: AppConfig.current.baseUrl);
  ref.onDispose(client.close);
  return client;
});

/// Navigation seam so controllers stay widget-free and tests can record
/// navigations instead of driving a real GoRouter.
typedef Navigate = void Function(String location);

final navigateProvider = Provider<Navigate>(
  (ref) => (location) => ref.read(routerProvider).go(location),
);

// -----------------------------------------------------------------------------
// Subjects list

class SubjectsNotifier extends AsyncNotifier<List<Subject>> {
  @override
  Future<List<Subject>> build() => ref.watch(apiProvider).listSubjects();

  /// Reloads the list; resolves when the fresh data (or the error) is in.
  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  /// Creates a subject and returns it so callers can navigate onward.
  Future<Subject> create(String title, {String? description}) async {
    final subject =
        await ref.read(apiProvider).createSubject(title, description: description);
    ref.invalidateSelf();
    return subject;
  }
}

final subjectsProvider =
    AsyncNotifierProvider<SubjectsNotifier, List<Subject>>(SubjectsNotifier.new);

// -----------------------------------------------------------------------------
// Onboarding chat

enum ChatRole { user, assistant }

/// One renderable bubble in the onboarding transcript.
class OnboardingChatEntry {
  const OnboardingChatEntry({
    required this.id,
    required this.role,
    required this.text,
    required this.timestamp,
    this.isTyping = false,
    this.isError = false,
    this.failedContent,
  });

  final int id;
  final ChatRole role;
  final String text;
  final DateTime timestamp;

  /// True for the transient "assistant is typing" bubble.
  final bool isTyping;

  /// True for delivery-failure bubbles that offer a Retry affordance.
  final bool isError;

  /// The user message whose delivery failed; non-null on retryable bubbles.
  final String? failedContent;

  OnboardingChatEntry copyWith({String? text}) => OnboardingChatEntry(
        id: id,
        role: role,
        text: text ?? this.text,
        timestamp: timestamp,
        isTyping: isTyping,
        isError: isError,
        failedContent: failedContent,
      );
}

/// Immutable view state owned by [OnboardingController].
class OnboardingViewState {
  const OnboardingViewState({
    this.entries = const [],
    this.isLoading = false,
    this.completeness,
    this.questionsAsked = 0,
    this.maxQuestions = 10,
    this.status = OnboardingStatus.onboarding,
    this.profile,
    this.showReadyBanner = false,
  });

  final List<OnboardingChatEntry> entries;
  final bool isLoading;
  final Completeness? completeness;
  final int questionsAsked;
  final int maxQuestions;
  final OnboardingStatus status;
  final OnboardingProfile? profile;

  /// One-shot flag: set when the backend flips status to ready so the screen
  /// can show a success banner before navigating to the ready route.
  final bool showReadyBanner;

  bool get isReady => status == OnboardingStatus.ready;

  OnboardingViewState copyWith({
    List<OnboardingChatEntry>? entries,
    bool? isLoading,
    Completeness? completeness,
    int? questionsAsked,
    int? maxQuestions,
    OnboardingStatus? status,
    OnboardingProfile? profile,
    bool? showReadyBanner,
  }) =>
      OnboardingViewState(
        entries: entries ?? this.entries,
        isLoading: isLoading ?? this.isLoading,
        completeness: completeness ?? this.completeness,
        questionsAsked: questionsAsked ?? this.questionsAsked,
        maxQuestions: maxQuestions ?? this.maxQuestions,
        status: status ?? this.status,
        profile: profile ?? this.profile,
        showReadyBanner: showReadyBanner ?? this.showReadyBanner,
      );
}

/// How long the "You're all set!" banner stays visible before routing to
/// `/subjects/:id/ready`.
const Duration readyBannerDuration = Duration(milliseconds: 1400);

/// Injectable so tests can collapse the banner wait.
final readyNavigationDelayProvider = Provider<Duration>(
  (ref) => readyBannerDuration,
);

class OnboardingController extends AsyncNotifier<OnboardingViewState> {
  OnboardingController(this.subjectId);

  final String subjectId;

  int _nextEntryId = 0;
  bool _disposed = false;

  OnboardingChatEntry _entry(
    ChatRole role,
    String text, {
    bool isTyping = false,
    bool isError = false,
    String? failedContent,
  }) =>
      OnboardingChatEntry(
        id: _nextEntryId++,
        role: role,
        text: text,
        timestamp: DateTime.now(),
        isTyping: isTyping,
        isError: isError,
        failedContent: failedContent,
      );

  @override
  Future<OnboardingViewState> build() async {
    ref.onDispose(() => _disposed = true);

    // Seed the transcript from the persisted server state.
    final remote = await ref.watch(apiProvider).getState(subjectId);
    final entries = <OnboardingChatEntry>[];
    for (final answer in remote.answers) {
      // The AI asked `question` first; the user's reply came after.
      entries.add(_entry(ChatRole.assistant, answer.question));
      entries.add(_entry(ChatRole.user, answer.answer));
    }
    return OnboardingViewState(
      entries: entries,
      completeness: remote.completeness,
      questionsAsked: remote.questionsAsked,
      maxQuestions: remote.maxQuestions,
      status: remote.status,
      profile: remote.profile,
    );
  }

  /// Sends a user message with an optimistic bubble + typing indicator.
  ///
  /// On success the indicator is replaced by the assistant reply. On failure
  /// an error bubble carrying a Retry affordance replaces it instead.
  Future<void> send(String content) async {
    final trimmed = content.trim();
    if (trimmed.isEmpty) return;
    final view = state.value;
    if (view == null || view.isLoading || view.isReady) return;

    final optimistic = [
      ...view.entries,
      _entry(ChatRole.user, trimmed),
      _entry(ChatRole.assistant, '', isTyping: true),
    ];
    state = AsyncData(
      view.copyWith(entries: optimistic, isLoading: true),
    );

    try {
      final turn = await ref.read(apiProvider).sendMessage(subjectId, trimmed);
      if (_disposed) return;
      final current = state.value!;
      final entries = [...current.entries];
      if (entries.isNotEmpty && entries.last.isTyping) entries.removeLast();
      entries.add(_entry(ChatRole.assistant, turn.reply));

      final becameReady = turn.status == OnboardingStatus.ready;
      state = AsyncData(current.copyWith(
        entries: entries,
        isLoading: false,
        completeness: turn.completeness,
        questionsAsked: turn.questionsAsked,
        maxQuestions: turn.maxQuestions,
        status: turn.status,
        profile: turn.profile,
        showReadyBanner: becameReady || current.showReadyBanner,
      ));
      if (becameReady && !current.isReady) _scheduleReadyNavigation();
    } on ApiException catch (error) {
      if (_disposed) return;
      final current = state.value;
      if (current == null) return;
      final entries = [...current.entries];
      if (entries.isNotEmpty && entries.last.isTyping) entries.removeLast();

      // Already finalized elsewhere → treat as ready and move on gracefully.
      if (error.isAlreadyFinalized) {
        state = AsyncData(current.copyWith(
          entries: entries,
          isLoading: false,
          status: OnboardingStatus.ready,
          showReadyBanner: true,
        ));
        _navigateToReady();
        return;
      }

      entries.add(_entry(
        ChatRole.assistant,
        _errorMessage(error),
        isError: true,
        failedContent: trimmed,
      ));
      state = AsyncData(current.copyWith(entries: entries, isLoading: false));
    }
  }

  /// Re-sends the message attached to a failed bubble after dropping it.
  Future<void> resendFailed(int entryId) async {
    final view = state.value;
    if (view == null || view.isLoading) return;
    final index = view.entries.indexWhere((entry) => entry.id == entryId);
    if (index < 0) return;
    final failed = view.entries[index].failedContent;
    if (failed == null) return;
    final entries = [...view.entries]..removeAt(index);
    state = AsyncData(view.copyWith(entries: entries));
    await send(failed);
  }

  void _scheduleReadyNavigation() {
    final delay = ref.read(readyNavigationDelayProvider);
    unawaited(Future.delayed(delay, () {
      if (_disposed) return;
      _navigateToReady();
    }));
  }

  void _navigateToReady() {
    if (_disposed) return;
    ref.read(navigateProvider)('/subjects/$subjectId/ready');
  }

  static String _errorMessage(ApiException error) {
    if (error.isNetwork) return error.message;
    return error.message;
  }
}

final onboardingControllerProvider =
    AsyncNotifierProvider.family<OnboardingController, OnboardingViewState, String>(
  OnboardingController.new,
);

/// Fresh server state for one subject (used by ReadyScreen).
final onboardingStateProvider =
    FutureProvider.family<OnboardingState, String>(
  (ref, subjectId) => ref.watch(apiProvider).getState(subjectId),
);
