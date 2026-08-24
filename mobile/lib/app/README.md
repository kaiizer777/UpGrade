# app/

Application-level composition root.

## Purpose
- Wires together `core` + `features` into a runnable app.
- Holds `app.dart` (MaterialApp / Router / Riverpod ProviderScope), route table, and top-level providers.
- No business logic — only composition, navigation, and environment bootstrapping.

## 2026 Clean Architecture (Feature-First, Riverpod Ready)
```
lib/app/
  app.dart        # root widget, Router + Theme + ProviderScope
  router.dart     # go_router / auto_route config (add when needed)
  providers.dart  # global Riverpod providers (e.g., app lifecycle)
```

## Conventions
- Keep `main.dart` tiny: `runApp(ProviderScope(child: App()))`.
- Riverpod: prefer `riverpod_generator` + `riverpod_annotation` when adding state.
- Add `flutter_riverpod` only when first feature needs it — scaffolding is ready.

## Next Steps
1. Create `lib/app/app.dart` exporting `App` widget.
2. Move Hello World from `main.dart` into `App`.
3. Add `lib/app/router.dart` when adding second screen.
