import 'dart:async';
import 'dart:math' as math;

import 'package:upgrade/features/onboarding/data/api_client.dart';
import 'package:upgrade/features/onboarding/domain/models.dart';

const String subjectId = 'subject-1';

Completeness completenessOf(int score) => Completeness(
      score: score,
      filledSlots: switch (score) {
        >= 60 => const ['goal'],
        _ => const <String>[],
      },
      missingSlots: switch (score) {
        >= 60 =>
          const ['current_level', 'background', 'motivation', 'pace_preference'],
        _ => const [
            'goal',
            'current_level',
            'background',
            'motivation',
            'pace_preference'
          ],
      },
    );

OnboardingState makeState({
  List<OnboardingAnswer> answers = const [],
  OnboardingStatus status = OnboardingStatus.onboarding,
  int score = 0,
  int questionsAsked = 0,
  int maxQuestions = 10,
  OnboardingProfile? profile,
}) =>
    OnboardingState(
      subjectId: subjectId,
      status: status,
      questionsAsked: questionsAsked,
      maxQuestions: maxQuestions,
      completeness: completenessOf(score),
      answers: answers,
      profile: profile,
    );

OnboardingAnswer answer(String question, String text, {int minutes = 0}) =>
    OnboardingAnswer(
      question: question,
      answer: text,
      createdAt: DateTime.utc(2026, 8, 24, 9, minutes),
    );

OnboardingTurn makeTurn({
  String reply = 'Great, next question…',
  OnboardingStatus status = OnboardingStatus.onboarding,
  int score = 20,
  int questionsAsked = 1,
  int maxQuestions = 10,
  OnboardingProfile? profile,
}) =>
    OnboardingTurn(
      reply: reply,
      status: status,
      questionsAsked: questionsAsked,
      maxQuestions: maxQuestions,
      completeness: completenessOf(score),
      profile: profile,
    );

OnboardingProfile makeProfile() => const OnboardingProfile(
      goal: 'Pass FAANG interviews in 3 months',
      currentLevel: 'Beginner',
      background: 'Self-taught web dev',
      motivation: 'Career switch',
      pacePreference: PacePreference.intense,
      status: OnboardingStatus.ready,
    );

/// Hand-rolled stand-in implementing the same surface as
/// [OnboardingApiClient]. No real HTTP ever leaves the process.
class FakeOnboardingApiClient implements OnboardingApiClient {
  FakeOnboardingApiClient({
    this.initialState,
    List<OnboardingTurn> turns = const [],
    this.seedError,
    this.sendError,
  }) : _scriptedTurns = turns;

  OnboardingState? initialState;
  final List<OnboardingTurn> _scriptedTurns;
  Object? seedError;
  Object? sendError;

  final List<String> sentMessages = [];
  Completer<void>? _gate;

  /// Makes the next [sendMessage] hang until [releaseNextSend] completes it.
  void gateNextSend() => _gate = Completer<void>();

  Future<void> releaseNextSend([Object? error]) {
    final gate = _gate;
    _gate = null;
    if (gate == null) return Future.value();
    if (error != null) {
      gate.completeError(error);
    } else {
      gate.complete();
    }
    return gate.future;
  }

  @override
  String get baseUrl => 'fake://api';

  @override
  Future<Subject> createSubject(String title, {String? description}) =>
      throw UnimplementedError();

  @override
  Future<List<Subject>> listSubjects() async => <Subject>[];

  @override
  Future<OnboardingState> getState(String subjectId) async {
    final error = seedError;
    if (error != null) throw error;
    return initialState ?? makeState();
  }

  @override
  Future<OnboardingTurn> sendMessage(String subjectId, String content) async {
    sentMessages.add(content);
    final gate = _gate;
    if (gate != null) await gate.future;
    final error = sendError;
    if (error != null) {
      sendError = null;
      throw error;
    }
    if (_scriptedTurns.isEmpty) return makeTurn();
    return _scriptedTurns[
        math.min(sentMessages.length - 1, _scriptedTurns.length - 1)];
  }

  @override
  void close() {}
}
