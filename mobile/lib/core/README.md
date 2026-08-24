# core/

Shared kernel — code used across features. No feature imports core backwards.

## Purpose
- Framework-agnostic utilities, design system, and cross-cutting concerns.
- Feature-first clean architecture: `core` is dependency-free; `features` depend on `core`.

## Structure
```
lib/core/
  config/   # env, flavors, AppConfig (dev/stg/prod)
  theme/    # ThemeData, AppColors, AppTextStyles, spacing tokens
  widgets/  # reusable UI (AppButton, AppScaffold, etc.)
  utils/    # extensions, formatters, validators, helpers
```

## 2026 Conventions (Riverpod Ready)
- No Riverpod providers with business logic here — only pure utilities and UI tokens.
- Theme: use Tailwind-like tokens or FlexColorScheme; expose via `ThemeExtension`.
- Config: `lib/core/config/app_config.dart` -> `AppConfig.fromEnvironment()` for API base URLs.
- Keep imports clean: `core` must not import `features/` or `app/`.

## Adding Dependencies
- When introducing `flutter_riverpod`, `dio`, `freezed`, keep their wrappers in `core` only if shared.
- Prefer `dart_mappable` / `freezed` for models; add lints via `analysis_options.yaml`.

## Placeholder Subfolders Created
- `config/` — env/flavor config
- `theme/`  — design tokens
- `widgets/` — shared widgets
- `utils/`  — extensions/helpers
