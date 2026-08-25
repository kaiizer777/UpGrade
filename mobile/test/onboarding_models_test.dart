import 'package:flutter_test/flutter_test.dart';
import 'package:upgrade/features/onboarding/domain/models.dart';

void main() {
  group('Subject', () {
    const createdJson = <String, Object?>{
      'id': 's-1',
      'title': 'DSA',
      'description': null,
      'created_at': '2026-08-24T10:30:00.000Z',
      // POST /subjects does not echo onboarding_status.
    };

    test('parses without onboarding_status, defaulting to onboarding', () {
      final subject = Subject.fromJson(createdJson);
      expect(subject.id, 's-1');
      expect(subject.title, 'DSA');
      expect(subject.description, isNull);
      expect(subject.createdAt, DateTime.parse('2026-08-24T10:30:00.000Z'));
      expect(subject.onboardingStatus, OnboardingStatus.onboarding);
    });

    test('round-trips with explicit status and description', () {
      const json = <String, Object?>{
        'id': 's-2',
        'title': 'Rust',
        'description': 'Systems programming',
        'created_at': '2026-08-24T08:00:00.000',
        'onboarding_status': 'ready',
      };
      final subject = Subject.fromJson(json);
      expect(subject.onboardingStatus, OnboardingStatus.ready);
      expect(subject.toJson(), json);
      expect(Subject.fromJson(subject.toJson()), subject);
    });
  });

  group('Completeness', () {
    test('round-trips slot lists', () {
      const json = <String, Object?>{
        'score': 60,
        'filled_slots': ['goal'],
        'missing_slots': ['current_level', 'background'],
      };
      final completeness = Completeness.fromJson(json);
      expect(completeness.score, 60);
      expect(completeness.filledSlots, ['goal']);
      expect(completeness.missingSlots, ['current_level', 'background']);
      expect(completeness.toJson(), json);
      expect(Completeness.fromJson(completeness.toJson()), completeness);
    });

    test('tolerates missing slot lists', () {
      final completeness =
          Completeness.fromJson(<String, Object?>{'score': 0});
      expect(completeness.filledSlots, isEmpty);
      expect(completeness.missingSlots, isEmpty);
    });
  });

  group('OnboardingProfile', () {
    test('round-trips all fields including pace enum', () {
      const json = <String, Object?>{
        'goal': 'Pass FAANG interviews in 3 months',
        'current_level': 'Beginner',
        'background': 'Self-taught web dev',
        'motivation': 'Career switch',
        'pace_preference': 'intense',
        'status': 'ready',
      };
      final profile = OnboardingProfile.fromJson(json);
      expect(profile.pacePreference, PacePreference.intense);
      expect(profile.status, OnboardingStatus.ready);
      expect(profile.toJson(), json);
      expect(OnboardingProfile.fromJson(profile.toJson()), profile);
    });

    test('accepts every pace value', () {
      for (final pace in PacePreference.values) {
        final profile = OnboardingProfile.fromJson(<String, Object?>{
          'goal': 'g',
          'current_level': 'l',
          'background': 'b',
          'motivation': 'm',
          'pace_preference': pace.name,
          'status': 'ready',
        });
        expect(profile.pacePreference, pace);
      }
    });

    test('rejects unknown pace value', () {
      expect(
        () => OnboardingProfile.fromJson(const <String, Object?>{
          'goal': 'g',
          'current_level': 'l',
          'background': 'b',
          'motivation': 'm',
          'pace_preference': 'blazing',
          'status': 'ready',
        }),
        throwsArgumentError,
      );
    });
  });

  group('OnboardingTurn', () {
    test('round-trips with profile present', () {
      final turn = makeTurnFixture(withProfile: true);
      final restored = OnboardingTurn.fromJson(turn.toJson());
      expect(restored, turn);
      expect(restored.profile!.pacePreference, PacePreference.steady);
      expect(restored.completeness.score, 80);
    });

    test('round-trips with null profile', () {
      final turn = makeTurnFixture();
      expect(turn.profile, isNull);
      expect(OnboardingTurn.fromJson(turn.toJson()), turn);
    });

    test('parses status transitions from the backend', () {
      final onboarding = makeTurnFixture(status: 'onboarding');
      final ready = makeTurnFixture(status: 'ready');
      expect(onboarding.status, OnboardingStatus.onboarding);
      expect(ready.status, OnboardingStatus.ready);
    });
  });

  group('OnboardingAnswer + OnboardingState', () {
    test('answer round-trips ISO datetime', () {
      const json = <String, Object?>{
        'question': 'What is your goal?',
        'answer': 'Interview prep',
        'created_at': '2026-08-24T09:05:00.000Z',
      };
      final answer = OnboardingAnswer.fromJson(json);
      expect(answer.createdAt, DateTime.utc(2026, 8, 24, 9, 5));
      expect(answer.toJson(), json);
    });

    test('state round-trips answers and profile', () {
      final state = OnboardingState(
        subjectId: 's-9',
        status: OnboardingStatus.onboarding,
        questionsAsked: 3,
        maxQuestions: 10,
        completeness: Completeness(
            score: 40, filledSlots: ['goal'], missingSlots: ['motivation']),
        answers: [
          OnboardingAnswer(
            question: 'What is your goal?',
            answer: 'Interview prep',
            createdAt: DateTime.utc(2026, 8, 24, 9, 0),
          ),
          OnboardingAnswer(
            question: 'Current level?',
            answer: 'Know arrays',
            createdAt: DateTime.utc(2026, 8, 24, 9, 4),
          ),
        ],
        profile: null,
      );

      final restored = OnboardingState.fromJson(state.toJson());
      expect(restored, state);
      expect(restored.subjectId, 's-9');
      expect(restored.answers, hasLength(2));
      expect(restored.answers[1].question, 'Current level?');
      expect(restored.profile, isNull);

      // And against the raw wire format:
      final wire = state.toJson();
      expect(wire['subject_id'], 's-9');
      expect(wire['questions_asked'], 3);
      expect(wire['max_questions'], 10);
      expect((wire['answers'] as List<Object?>), hasLength(2));
    });
  });
}

OnboardingTurn makeTurnFixture({
  bool withProfile = false,
  String status = 'onboarding',
}) =>
    OnboardingTurn.fromJson(<String, Object?>{
      'reply': 'Noted. How many hours per week?',
      'status': status,
      'questions_asked': 2,
      'max_questions': 10,
      'completeness': <String, Object?>{
        'score': 80,
        'filled_slots': ['goal', 'motivation'],
        'missing_slots': <String>[],
      },
      'profile': withProfile
          ? <String, Object?>{
              'goal': 'Build a CLI tool',
              'current_level': 'Intermediate',
              'background': 'CS student',
              'motivation': 'Side project',
              'pace_preference': 'steady',
              'status': 'ready',
            }
          : null,
    });
