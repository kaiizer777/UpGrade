import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../onboarding/domain/models.dart';
import '../../../onboarding/presentation/providers.dart';
import '../../../roadmap/presentation/providers.dart';

/// Horizontally scrollable pill/tab bar listing all subjects.
///
/// - Fetches subjects via [subjectsProvider].
/// - Shows a status chip per subject: `Onboarding` / `Ready` / active topic title.
/// - Selected pill is highlighted with the primary colour.
/// - Tap invokes [onSelected] if provided, otherwise navigates to
///   `/subjects/<id>/feed` (or `/onboarding` when still onboarding).
///
/// Reusable across Feed, Roadmap and Subjects screens.
class SubjectSwitcher extends ConsumerWidget {
  const SubjectSwitcher({
    super.key,
    required this.selectedSubjectId,
    this.onSelected,
  });

  final String selectedSubjectId;
  final ValueChanged<String>? onSelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final subjectsAsync = ref.watch(subjectsProvider);

    return subjectsAsync.when(
      loading: () => const SizedBox(
        key: Key('subject-switcher-loading'),
        height: 48,
        child: Center(child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))),
      ),
      error: (error, _) => _ErrorBar(
        key: const Key('subject-switcher-error'),
        message: error.toString(),
        onRetry: () => ref.invalidate(subjectsProvider),
      ),
      data: (subjects) {
        if (subjects.isEmpty) {
          return const SizedBox.shrink(key: Key('subject-switcher-empty'));
        }
        return Container(
          key: const Key('subject-switcher'),
          height: 56,
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: ListView.separated(
            key: const Key('subject-switcher-list'),
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            itemCount: subjects.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, index) {
              final subject = subjects[index];
              final isSelected = subject.id == selectedSubjectId;
              return _SubjectPill(
                key: ValueKey('subject-pill-${subject.id}'),
                subject: subject,
                isSelected: isSelected,
                onTap: () {
                  if (subject.id == selectedSubjectId) return;
                  if (onSelected != null) {
                    onSelected!(subject.id);
                    return;
                  }
                  // Default navigation: onboarding subjects go to onboarding,
                  // otherwise to feed (feed context swaps to active topic).
                  final loc = subject.onboardingStatus == OnboardingStatus.ready
                      ? '/subjects/${subject.id}/feed'
                      : '/subjects/${subject.id}/onboarding';
                  context.go(loc);
                },
              );
            },
          ),
        );
      },
    );
  }
}

class _SubjectPill extends ConsumerWidget {
  const _SubjectPill({
    super.key,
    required this.subject,
    required this.isSelected,
    required this.onTap,
  });

  final Subject subject;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    // For ready subjects, try to resolve active topic title for the chip.
    String chipLabel;
    IconData chipIcon;
    if (subject.onboardingStatus == OnboardingStatus.ready) {
      chipLabel = 'Ready';
      chipIcon = Icons.check_circle;
      final roadmapAsync = ref.watch(roadmapProvider(subject.id));
      final enriched = roadmapAsync.maybeWhen(
        data: (roadmap) {
          if (roadmap.topics.isEmpty) return null;
          final active = roadmap.topics.where((t) => t.status.name == 'active').toList();
          final title = active.isNotEmpty ? active.first.title : roadmap.topics.first.title;
          return title.length > 18 ? '${title.substring(0, 16)}…' : title;
        },
        orElse: () => null,
      );
      if (enriched != null) {
        chipLabel = enriched;
        // Use active icon when we have a roadmap-derived title
        chipIcon = roadmapAsync.maybeWhen(
          data: (r) => r.topics.any((t) => t.status.name == 'active') ? Icons.play_circle_filled : Icons.schedule,
          orElse: () => Icons.check_circle,
        );
      }
    } else {
      chipLabel = 'Onboarding';
      chipIcon = Icons.autorenew;
    }

    final bg = isSelected ? colorScheme.primary : colorScheme.surfaceContainerHighest;
    final fg = isSelected ? colorScheme.onPrimary : colorScheme.onSurfaceVariant;
    final borderColor = isSelected ? colorScheme.primary : colorScheme.outlineVariant;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        key: ValueKey('subject-pill-tap-${subject.id}'),
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: borderColor),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Avatar letter
              Container(
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                  color: isSelected ? Colors.white.withValues(alpha: 0.22) : colorScheme.primary.withValues(alpha: 0.14),
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Text(
                  subject.title.isEmpty ? '?' : subject.title[0].toUpperCase(),
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: fg),
                ),
              ),
              const SizedBox(width: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 120),
                child: Text(
                  subject.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: fg,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Container(
                key: ValueKey('pill-chip-${subject.id}'),
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: isSelected ? Colors.white.withValues(alpha: 0.20) : colorScheme.surface,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(chipIcon, size: 11, color: fg.withValues(alpha: 0.9)),
                    const SizedBox(width: 4),
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 90),
                      child: Text(
                        chipLabel,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w600, color: fg.withValues(alpha: 0.9)),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorBar extends StatelessWidget {
  const _ErrorBar({super.key, required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Row(
        children: [
          Icon(Icons.cloud_off_outlined, size: 18, color: colorScheme.error),
          const SizedBox(width: 8),
          Expanded(child: Text(message, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: colorScheme.error, fontSize: 12))),
          const SizedBox(width: 8),
          FilledButton.tonalIcon(
            key: const Key('subject-switcher-retry'),
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 14),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}
