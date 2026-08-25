import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/api_client.dart';
import '../../domain/models.dart';
import '../../../subjects/presentation/widgets/subject_switcher.dart';
import '../providers.dart';

/// `/` — lists every subject; FAB opens the create sheet.
///
/// Highlight fix: [SubjectSwitcher] now receives the *actual* selected id
/// (local state, updated on tap) instead of `list.first.id`, so the correct
/// pill is highlighted. Detail screens (roadmap/feed) already pass
/// `widget.subjectId` from the router param.
class SubjectsScreen extends ConsumerStatefulWidget {
  const SubjectsScreen({super.key, this.selectedSubjectId});

  /// Optional router-provided id. When `/` is used without a param it is null
  /// and no pill is pre-selected (fixes `list.first.id` highlight bug).
  final String? selectedSubjectId;

  @override
  ConsumerState<SubjectsScreen> createState() => _SubjectsScreenState();
}

class _SubjectsScreenState extends ConsumerState<SubjectsScreen> {
  String? _localSelectedId;

  @override
  Widget build(BuildContext context) {
    final subjects = ref.watch(subjectsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('UpGrade'),
        centerTitle: false,
      ),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('subjects-fab'),
        onPressed: () => _openCreateSheet(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('New subject'),
      ),
      body: subjects.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _ErrorView(
          message: error is ApiException ? error.message : error.toString(),
          onRetry: () => ref.read(subjectsProvider.notifier).refresh(),
        ),
        data: (list) {
          if (list.isEmpty) return const _EmptyState();
          // Derive the actual selected id: widget prop > local tap state > none.
          // Never default to list.first.id — that was the highlight bug.
          final String effectiveSelected;
          if (widget.selectedSubjectId != null && list.any((s) => s.id == widget.selectedSubjectId)) {
            effectiveSelected = widget.selectedSubjectId!;
          } else if (_localSelectedId != null && list.any((s) => s.id == _localSelectedId)) {
            effectiveSelected = _localSelectedId!;
          } else {
            effectiveSelected = '';
          }
          return Column(
            children: [
              if (list.length > 1)
                SubjectSwitcher(
                  selectedSubjectId: effectiveSelected,
                  onSelected: (newId) {
                    setState(() => _localSelectedId = newId);
                    final target = list.firstWhere((s) => s.id == newId, orElse: () => list.first);
                    _openSubject(context, target);
                  },
                ),
              Expanded(
                child: RefreshIndicator(
                  onRefresh: () => ref.read(subjectsProvider.notifier).refresh(),
                  child: ListView.separated(
                    key: const Key('subjects-list'),
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
                    itemCount: list.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final subject = list[index];
                      return _SubjectCard(
                        key: ValueKey('subject-${subject.id}'),
                        subject: subject,
                        onTap: () => _openSubject(context, subject),
                      );
                    },
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  void _openSubject(BuildContext context, Subject subject) {
    switch (subject.onboardingStatus) {
      case OnboardingStatus.ready:
        context.push('/subjects/${subject.id}/ready');
      case OnboardingStatus.onboarding:
        context.push('/subjects/${subject.id}/onboarding');
    }
  }

  Future<void> _openCreateSheet(BuildContext context, WidgetRef ref) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => const _CreateSubjectSheet(),
    );
  }
}

class _SubjectCard extends StatelessWidget {
  const _SubjectCard({super.key, required this.subject, required this.onTap});

  final Subject subject;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final ready = subject.onboardingStatus == OnboardingStatus.ready;

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: colorScheme.outlineVariant),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        onTap: onTap,
        leading: CircleAvatar(
          backgroundColor:
              ready ? colorScheme.primaryContainer : colorScheme.secondaryContainer,
          foregroundColor:
              ready ? colorScheme.onPrimaryContainer : colorScheme.onSecondaryContainer,
          child: Text(
            subject.title.isEmpty ? '?' : subject.title[0].toUpperCase(),
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ),
        title: Text(
          subject.title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Align(
            alignment: Alignment.centerLeft,
            child: _StatusChip(ready: ready),
          ),
        ),
        trailing: Icon(Icons.chevron_right, color: colorScheme.outline),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.ready});

  final bool ready;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      key: ready ? const Key('status-chip-ready') : const Key('status-chip-onboarding'),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: ready
            ? colorScheme.primaryContainer.withValues(alpha: 0.7)
            : colorScheme.tertiaryContainer.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            ready ? Icons.check_circle : Icons.autorenew,
            size: 13,
            color: ready ? colorScheme.onPrimaryContainer : colorScheme.onTertiaryContainer,
          ),
          const SizedBox(width: 4),
          Text(
            ready ? 'Ready' : 'Onboarding',
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: ready ? colorScheme.onPrimaryContainer : colorScheme.onTertiaryContainer,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      key: const Key('subjects-empty-state'),
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.school_outlined, size: 72, color: colorScheme.primary),
            const SizedBox(height: 16),
            Text('What do you want to learn next?', style: textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              'Create a subject and UpGrade\'s AI will interview you briefly, '
              'then build a study plan that actually fits you.',
              textAlign: TextAlign.center,
              style: textTheme.bodyMedium?.copyWith(color: colorScheme.outline),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.cloud_off_outlined, size: 64, color: colorScheme.error),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.tonalIcon(
              key: const Key('subjects-retry'),
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}

class _CreateSubjectSheet extends ConsumerStatefulWidget {
  const _CreateSubjectSheet();

  @override
  ConsumerState<_CreateSubjectSheet> createState() => _CreateSubjectSheetState();
}

class _CreateSubjectSheetState extends ConsumerState<_CreateSubjectSheet> {
  final _controller = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final title = _controller.text.trim();
    if (title.isEmpty || _submitting) return;
    setState(() => _submitting = true);
    try {
      final subject = await ref.read(subjectsProvider.notifier).create(title);
      if (!mounted) return;
      Navigator.of(context).pop();
      context.push('/subjects/${subject.id}/onboarding');
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _submitting = false);
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(error.message)));
    } on Exception {
      if (!mounted) return;
      setState(() => _submitting = false);
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(const SnackBar(content: Text('Something went wrong. Try again.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final viewInsets = MediaQuery.of(context).viewInsets.bottom;
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: EdgeInsets.only(left: 20, right: 20, top: 20, bottom: 20 + viewInsets),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('New subject', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(
            'Tell UpGrade what you want to learn.',
            style: Theme.of(context)
                .textTheme
                .bodySmall
                ?.copyWith(color: colorScheme.outline),
          ),
          const SizedBox(height: 16),
          TextField(
            key: const Key('create-subject-field'),
            controller: _controller,
            autofocus: true,
            enabled: !_submitting,
            minLines: 1,
            maxLines: 3,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _submit(),
            decoration: InputDecoration(
              hintText: 'What do you want to learn?',
              border: const OutlineInputBorder(),
              prefixIcon: const Icon(Icons.travel_explore_outlined),
              errorText: null,
              filled: true,
            ),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            key: const Key('create-subject-submit'),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            onPressed: _submitting ? null : _submit,
            icon: _submitting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.auto_awesome),
            label: Text(_submitting ? 'Creating…' : 'Start learning'),
          ),
        ],
      ),
    );
  }
}
