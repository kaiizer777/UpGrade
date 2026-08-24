# l10n/

Localization (i18n) placeholder.

## Purpose
- Holds ARB files and generated localizations.
- Run `flutter gen-l10n` after adding `l10n.yaml`.

## Setup (when needed)
1. Create `l10n.yaml` at project root:
```yaml
arb-dir: lib/l10n
template-arb-file: app_en.arb
output-localization-file: app_localizations.dart
```
2. Add `app_en.arb`, `app_fr.arb`, etc.
3. Enable `generate: true` in `pubspec.yaml` flutter section.

Currently empty — safe to ignore until i18n required.
