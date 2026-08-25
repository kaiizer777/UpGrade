/// Pure domain models for the onboarding feature.
///
/// No IO here: JSON mapping only, with snake_case keys exactly matching the
/// backend contract.
library;

enum OnboardingStatus { onboarding, ready }

enum PacePreference { chill, steady, intense }

OnboardingStatus _statusFromJson(Object? value) {
  if (value is! String) {
    throw ArgumentError.value(value, 'status', 'Expected a string');
  }
  return OnboardingStatus.values.byName(value);
}

PacePreference? _paceFromJson(Object? value) {
  if (value == null) return null;
  if (value is! String) {
    throw ArgumentError.value(value, 'pace_preference', 'Expected a string');
  }
  return PacePreference.values.byName(value);
}

bool _listEquals<T>(List<T> a, List<T> b) {
  if (identical(a, b)) return true;
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

class Subject {
  const Subject({
    required this.id,
    required this.title,
    required this.description,
    required this.createdAt,
    required this.onboardingStatus,
  });

  factory Subject.fromJson(Map<Object?, Object?> json) => Subject(
        id: json['id'] as String,
        title: json['title'] as String,
        description: json['description'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        // POST /subjects does not echo onboarding_status yet; new subjects
        // always start in the "onboarding" state per contract.
        onboardingStatus: json['onboarding_status'] == null
            ? OnboardingStatus.onboarding
            : _statusFromJson(json['onboarding_status']),
      );

  final String id;
  final String title;
  final String? description;
  final DateTime createdAt;
  final OnboardingStatus onboardingStatus;

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'title': title,
        'description': description,
        'created_at': createdAt.toIso8601String(),
        'onboarding_status': onboardingStatus.name,
      };

  Subject copyWith({
    String? id,
    String? title,
    Object? description = _sentinel,
    DateTime? createdAt,
    OnboardingStatus? onboardingStatus,
  }) =>
      Subject(
        id: id ?? this.id,
        title: title ?? this.title,
        description:
            identical(description, _sentinel) ? this.description : description as String?,
        createdAt: createdAt ?? this.createdAt,
        onboardingStatus: onboardingStatus ?? this.onboardingStatus,
      );

  static const _sentinel = Object();

  @override
  bool operator ==(Object other) =>
      identical(other, this) ||
      other is Subject &&
          other.id == id &&
          other.title == title &&
          other.description == description &&
          other.createdAt == createdAt &&
          other.onboardingStatus == onboardingStatus;

  @override
  int get hashCode =>
      Object.hash(id, title, description, createdAt, onboardingStatus);
}

class Completeness {
  const Completeness({
    required this.score,
    required this.filledSlots,
    required this.missingSlots,
  });

  factory Completeness.fromJson(Map<Object?, Object?> json) => Completeness(
        score: json['score'] as int,
        filledSlots: _strings(json['filled_slots']),
        missingSlots: _strings(json['missing_slots']),
      );

  static List<String> _strings(Object? value) =>
      (value as List<Object?>? ?? const []).cast<String>();

  final int score;
  final List<String> filledSlots;
  final List<String> missingSlots;

  Map<String, Object?> toJson() => <String, Object?>{
        'score': score,
        'filled_slots': filledSlots,
        'missing_slots': missingSlots,
      };

  @override
  bool operator ==(Object other) =>
      identical(other, this) ||
      other is Completeness &&
          other.score == score &&
          _listEquals(other.filledSlots, filledSlots) &&
          _listEquals(other.missingSlots, missingSlots);

  @override
  int get hashCode => Object.hash(score, filledSlots, missingSlots);
}

class OnboardingProfile {
  const OnboardingProfile({
    required this.goal,
    required this.currentLevel,
    required this.background,
    required this.motivation,
    required this.pacePreference,
    required this.status,
  });

  factory OnboardingProfile.fromJson(Map<Object?, Object?> json) =>
      OnboardingProfile(
        goal: json['goal'] as String,
        currentLevel: json['current_level'] as String,
        background: json['background'] as String,
        motivation: json['motivation'] as String,
        pacePreference: _paceFromJson(json['pace_preference']),
        status: _statusFromJson(json['status']),
      );

  final String goal;
  final String currentLevel;
  final String background;
  final String motivation;
  final PacePreference? pacePreference;
  final OnboardingStatus status;

  Map<String, Object?> toJson() => <String, Object?>{
        'goal': goal,
        'current_level': currentLevel,
        'background': background,
        'motivation': motivation,
        'pace_preference': pacePreference?.name,
        'status': status.name,
      };

  @override
  bool operator ==(Object other) =>
      identical(other, this) ||
      other is OnboardingProfile &&
          other.goal == goal &&
          other.currentLevel == currentLevel &&
          other.background == background &&
          other.motivation == motivation &&
          other.pacePreference == pacePreference &&
          other.status == status;

  @override
  int get hashCode =>
      Object.hash(goal, currentLevel, background, motivation, pacePreference, status);
}

/// One assistant turn returned by POST .../onboarding/messages.
class OnboardingTurn {
  const OnboardingTurn({
    required this.reply,
    required this.status,
    required this.questionsAsked,
    required this.maxQuestions,
    required this.completeness,
    required this.profile,
  });

  factory OnboardingTurn.fromJson(Map<Object?, Object?> json) => OnboardingTurn(
        reply: json['reply'] as String,
        status: _statusFromJson(json['status']),
        questionsAsked: json['questions_asked'] as int,
        maxQuestions: json['max_questions'] as int,
        completeness:
            Completeness.fromJson(json['completeness'] as Map<Object?, Object?>),
        profile: json['profile'] == null
            ? null
            : OnboardingProfile.fromJson(json['profile'] as Map<Object?, Object?>),
      );

  final String reply;
  final OnboardingStatus status;
  final int questionsAsked;
  final int maxQuestions;
  final Completeness completeness;
  final OnboardingProfile? profile;

  Map<String, Object?> toJson() => <String, Object?>{
        'reply': reply,
        'status': status.name,
        'questions_asked': questionsAsked,
        'max_questions': maxQuestions,
        'completeness': completeness.toJson(),
        'profile': profile?.toJson(),
      };

  @override
  bool operator ==(Object other) =>
      identical(other, this) ||
      other is OnboardingTurn &&
          other.reply == reply &&
          other.status == status &&
          other.questionsAsked == questionsAsked &&
          other.maxQuestions == maxQuestions &&
          other.completeness == completeness &&
          other.profile == profile;

  @override
  int get hashCode => Object.hash(reply, status, questionsAsked, maxQuestions,
      completeness, profile);
}

/// A stored Q&A pair from GET .../onboarding/state.
class OnboardingAnswer {
  const OnboardingAnswer({
    required this.question,
    required this.answer,
    required this.createdAt,
  });

  factory OnboardingAnswer.fromJson(Map<Object?, Object?> json) =>
      OnboardingAnswer(
        question: json['question'] as String,
        answer: json['answer'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  final String question;
  final String answer;
  final DateTime createdAt;

  Map<String, Object?> toJson() => <String, Object?>{
        'question': question,
        'answer': answer,
        'created_at': createdAt.toIso8601String(),
      };

  @override
  bool operator ==(Object other) =>
      identical(other, this) ||
      other is OnboardingAnswer &&
          other.question == question &&
          other.answer == answer &&
          other.createdAt == createdAt;

  @override
  int get hashCode => Object.hash(question, answer, createdAt);
}

/// Full persisted onboarding state returned by GET .../onboarding/state.
class OnboardingState {
  const OnboardingState({
    required this.subjectId,
    required this.status,
    required this.questionsAsked,
    required this.maxQuestions,
    required this.completeness,
    required this.answers,
    required this.profile,
  });

  factory OnboardingState.fromJson(Map<Object?, Object?> json) =>
      OnboardingState(
        subjectId: json['subject_id'] as String,
        status: _statusFromJson(json['status']),
        questionsAsked: json['questions_asked'] as int,
        maxQuestions: json['max_questions'] as int,
        completeness:
            Completeness.fromJson(json['completeness'] as Map<Object?, Object?>),
        answers: ((json['answers'] as List<Object?>?) ?? const [])
            .cast<Map<Object?, Object?>>()
            .map(OnboardingAnswer.fromJson)
            .toList(growable: false),
        profile: json['profile'] == null
            ? null
            : OnboardingProfile.fromJson(json['profile'] as Map<Object?, Object?>),
      );

  final String subjectId;
  final OnboardingStatus status;
  final int questionsAsked;
  final int maxQuestions;
  final Completeness completeness;
  final List<OnboardingAnswer> answers;
  final OnboardingProfile? profile;

  Map<String, Object?> toJson() => <String, Object?>{
        'subject_id': subjectId,
        'status': status.name,
        'questions_asked': questionsAsked,
        'max_questions': maxQuestions,
        'completeness': completeness.toJson(),
        'answers': [for (final answer in answers) answer.toJson()],
        'profile': profile?.toJson(),
      };

  @override
  bool operator ==(Object other) =>
      identical(other, this) ||
      other is OnboardingState &&
          other.subjectId == subjectId &&
          other.status == status &&
          other.questionsAsked == questionsAsked &&
          other.maxQuestions == maxQuestions &&
          other.completeness == completeness &&
          _listEquals(other.answers, answers) &&
          other.profile == profile;

  @override
  int get hashCode => Object.hash(subjectId, status, questionsAsked,
      maxQuestions, completeness, answers, profile);
}
