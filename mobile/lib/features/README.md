# features/

Feature-first clean architecture. Each feature is vertical slice: data / domain / presentation.

## Purpose
- Isolation: features do not import each other directly; share via `core` or explicit interfaces.
- Scales with team: one folder per business capability (e.g., `learning`, `auth`, `profile`).

## Structure (per feature)
```
lib/features/<feature>/
  data/         # repositories impl, data sources (api/local), DTOs, mappers
  domain/       # entities, repository interfaces, use-cases / notifiers, pure logic
  presentation/ # widgets, pages, Riverpod providers, controllers
```

## Example: learning (scaffolded)
```
lib/features/learning/
  data/
  domain/
  presentation/
```
Add as needed:
- `learning/domain/entities/lesson.dart`
- `learning/data/repositories/learning_repository_impl.dart`
- `learning/presentation/pages/learning_page.dart`
- `learning/presentation/providers/learning_provider.dart` (Riverpod)

## 2026 Conventions (Riverpod Ready)
- State: use `riverpod_generator` + `AsyncNotifier`/`Notifier`. No `StateProvider` for logic.
- Data: repository interface in `domain/`, implementation in `data/`. Inject via Riverpod.
- Testing: mirrors lib structure under `test/features/<feature>/`.
- Do not import `app/` from here; import only `core/` and Flutter/Dart SDK.

## Adding a New Feature
1. `lib/features/<name>/{data,domain,presentation}/`
2. Define entity + repo interface in `domain/`
3. Implement repo in `data/` + Riverpod provider in `presentation/providers/`
