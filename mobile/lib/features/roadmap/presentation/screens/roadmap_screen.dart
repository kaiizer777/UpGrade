import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/api_client.dart';
import '../../domain/models.dart';
import '../../../subjects/presentation/widgets/subject_switcher.dart';
import '../providers.dart';

class RoadmapScreen extends ConsumerStatefulWidget {
  const RoadmapScreen({super.key, required this.subjectId});

  final String subjectId;

  @override
  ConsumerState<RoadmapScreen> createState() => _RoadmapScreenState();
}

class _RoadmapScreenState extends ConsumerState<RoadmapScreen> {
  bool _isGenerating = false;
  String? _errorText;

  Future<void> _generate() async {
    setState(() {
      _isGenerating = true;
      _errorText = null;
    });
    try {
      await ref.read(roadmapApiProvider).generateRoadmap(widget.subjectId);
      ref.invalidate(roadmapProvider(widget.subjectId));
      if (mounted) {
        // Wait for refresh to complete so tests can observe new data
        await ref.read(roadmapProvider(widget.subjectId).future);
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.isOnboardingNotReady) {
        setState(() => _errorText = 'Complete onboarding first');
      } else if (e.isServerError) {
        setState(() => _errorText = e.message);
        if (mounted) {
          ScaffoldMessenger.of(context)
            ..hideCurrentSnackBar()
            ..showSnackBar(SnackBar(content: Text(e.message)));
        }
      } else {
        setState(() => _errorText = e.message);
        if (mounted) {
          ScaffoldMessenger.of(context)
            ..hideCurrentSnackBar()
            ..showSnackBar(SnackBar(content: Text(e.message)));
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _errorText = e.toString());
      }
    } finally {
      if (mounted) {
        setState(() => _isGenerating = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final asyncRoadmap = ref.watch(roadmapProvider(widget.subjectId));
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Your roadmap')),
      body: asyncRoadmap.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) {
          final isApi = error is ApiException;
          final msg = isApi ? error.message : error.toString();
          final is409 = isApi && error.isOnboardingNotReady;
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    is409 ? Icons.assignment_outlined : Icons.cloud_off_outlined,
                    size: 56,
                    color: is409 ? colorScheme.primary : colorScheme.error,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    msg,
                    textAlign: TextAlign.center,
                    key: const Key('roadmap-error-text'),
                  ),
                  if (is409) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Complete onboarding first',
                      key: const Key('roadmap-409-text'),
                      style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.outline),
                    ),
                  ],
                  const SizedBox(height: 16),
                  if (is409)
                    FilledButton.icon(
                      key: const Key('roadmap-back-to-onboarding'),
                      onPressed: () => context.go('/subjects/${widget.subjectId}/onboarding'),
                      icon: const Icon(Icons.chat_bubble_outline),
                      label: const Text('Back to onboarding'),
                    )
                  else
                    FilledButton.tonalIcon(
                      key: const Key('roadmap-retry'),
                      onPressed: () => ref.invalidate(roadmapProvider(widget.subjectId)),
                      icon: const Icon(Icons.refresh),
                      label: const Text('Try again'),
                    ),
                ],
              ),
            ),
          );
        },
        data: (roadmap) {
          if (_errorText != null) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted && _errorText != null && !_isGenerating) {
                // Show inline error already handled via state
              }
            });
          }

          if (roadmap.topics.isEmpty) {
            return Column(
              children: [
                SubjectSwitcher(
                  selectedSubjectId: widget.subjectId,
                  onSelected: (newId) => context.go('/subjects/$newId/roadmap'),
                ),
                Expanded(
                  child: Center(
                    key: const Key('roadmap-empty'),
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.map_outlined, size: 64, color: colorScheme.primary),
                          const SizedBox(height: 16),
                          Text(
                            'Your learning path is not ready yet.',
                            style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Generate your personalized roadmap — tailored to your goal, level and pace.',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.outline),
                          ),
                          const SizedBox(height: 20),
                          if (_errorText != null) ...[
                            Text(
                              _errorText!,
                              key: const Key('roadmap-generate-error'),
                              textAlign: TextAlign.center,
                              style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.error),
                            ),
                            const SizedBox(height: 12),
                          ],
                          FilledButton.icon(
                            key: const Key('roadmap-generate'),
                            onPressed: _isGenerating ? null : _generate,
                            icon: _isGenerating
                                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                                : const Icon(Icons.auto_awesome),
                            label: Text(_isGenerating ? 'Generating…' : 'Generate your personalized roadmap'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            );
          }

          // Populated roadmap
          return Column(
            children: [
              SubjectSwitcher(
                selectedSubjectId: widget.subjectId,
                onSelected: (newId) => context.go('/subjects/$newId/roadmap'),
              ),
              Expanded(
                child: ListView.separated(
                  key: const Key('roadmap-list'),
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
                  itemCount: roadmap.topics.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final topic = roadmap.topics[index];
                    final isActive = topic.status == TopicStatus.active;
                    final isDone = topic.status == TopicStatus.done;
                    return Card(
                      key: ValueKey('topic-${topic.id}'),
                      elevation: isActive ? 3 : 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                        side: BorderSide(
                          color: isActive ? colorScheme.primary.withValues(alpha: 0.4) : colorScheme.outlineVariant,
                        ),
                      ),
                      color: isActive ? colorScheme.primaryContainer.withValues(alpha: 0.35) : null,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              key: ValueKey('badge-${topic.orderIndex}'),
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                color: isActive
                                    ? colorScheme.primary
                                    : isDone
                                        ? Colors.green.shade600
                                        : colorScheme.surfaceContainerHighest,
                                shape: BoxShape.circle,
                              ),
                              alignment: Alignment.center,
                              child: Text(
                                '${topic.orderIndex}',
                                style: TextStyle(
                                  color: isActive || isDone ? Colors.white : colorScheme.onSurfaceVariant,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    topic.title,
                                    style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    topic.prerequisiteIds.isEmpty
                                        ? 'No prerequisites'
                                        : 'Requires: ${topic.prerequisiteIds.map((e) => e.toString()).join(", ")}',
                                    key: ValueKey('prereq-${topic.id}'),
                                    style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.outline),
                                  ),
                                  // For spec: also show order-based prerequisite trail if prerequisite_ids empty but logical prereqs exist? We show ids for now.
                                  // Show status chip
                                  const SizedBox(height: 6),
                                  _StatusChip(status: topic.status),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (_isGenerating) const LinearProgressIndicator(key: Key('roadmap-generating-bar')),
                    const SizedBox(height: 8),
                    FilledButton.icon(
                      key: const Key('start-learning'),
                      onPressed: () {
                        try {
                          context.go('/subjects/${widget.subjectId}/feed');
                        } catch (_) {
                          ScaffoldMessenger.of(context)
                            ..hideCurrentSnackBar()
                            ..showSnackBar(const SnackBar(content: Text('Feed coming in Phase 5')));
                        }
                      },
                      icon: const Icon(Icons.play_arrow_rounded),
                      label: const Text('Start learning →'),
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final TopicStatus status;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final (label, color, icon) = switch (status) {
      TopicStatus.active => ('Active', colorScheme.primary, Icons.play_circle_filled),
      TopicStatus.pending => ('Pending', colorScheme.outline, Icons.schedule),
      TopicStatus.done => ('Done', Colors.green.shade600, Icons.check_circle),
    };
    final isActive = status == TopicStatus.active;
    final isDone = status == TopicStatus.done;
    return Container(
      key: Key('status-chip-${status.name}'),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: isActive
            ? colorScheme.primaryContainer.withValues(alpha: 0.7)
            : isDone
                ? Colors.green.withValues(alpha: 0.15)
                : colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color),
          ),
        ],
      ),
    );
  }
}
