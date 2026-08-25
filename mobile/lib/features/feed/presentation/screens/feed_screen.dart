import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;

import '../../../../core/config/app_config.dart';
import '../../../chat/presentation/widgets/chat_sheet.dart';
import '../../../subjects/presentation/widgets/subject_switcher.dart';
import '../providers.dart';

class FeedScreen extends ConsumerStatefulWidget {
  const FeedScreen({super.key, required this.subjectId});
  final String subjectId;

  @override
  ConsumerState<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends ConsumerState<FeedScreen> {
  final ScrollController _scrollController = ScrollController();
  bool _prefetchTriggered = false;
  bool _completing = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final max = _scrollController.position.maxScrollExtent;
    final current = _scrollController.position.pixels;
    if (max == 0) return;
    final progress = current / max;
    if (progress >= 0.7 && !_prefetchTriggered) {
      _triggerPrefetch();
    }
  }

  Future<void> _triggerPrefetch() async {
    if (_prefetchTriggered) return;
    final feed = ref.read(feedProvider(widget.subjectId)).asData?.value;
    if (feed == null || feed.topic == null) return;
    _prefetchTriggered = true;
    try {
      final baseUrl = AppConfig.current.baseUrl;
      final uri = Uri.parse('$baseUrl/subjects/${widget.subjectId}/roadmap');
      final resp = await http.get(uri, headers: {'accept': 'application/json'});
      if (resp.statusCode == 200) {
        final data = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
        final topics = (data['topics'] as List).cast<Map<String, dynamic>>();
        final idx = topics.indexWhere((t) => t['id'] == feed.topic!.id);
        if (idx != -1 && idx + 1 < topics.length) {
          final next = topics[idx + 1];
          final nextId = next['id'] as int;
          final nextStatus = next['status'] as String;
          if (nextStatus == 'pending') {
            await ref.read(feedApiProvider).prefetch(widget.subjectId, nextId);
          }
        }
      }
    } catch (_) {}
  }

  Future<void> _complete() async {
    final feed = ref.read(feedProvider(widget.subjectId)).asData?.value;
    if (feed == null || feed.topic == null) return;
    setState(() => _completing = true);
    try {
      final result = await ref.read(feedApiProvider).completeTopic(feed.topic!.id);
      if (!mounted) return;
      ref.invalidate(feedProvider(widget.subjectId));
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(
          content: Text(result.allCompleted ? 'All topics completed!' : 'Completed ${feed.topic!.title} -> ${result.nextTopicTitle ?? 'next'}'),
        ));
      _prefetchTriggered = false;
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Complete failed: $e')));
    } finally {
      if (mounted) setState(() => _completing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final feedAsync = ref.watch(feedProvider(widget.subjectId));
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Feed'),
        actions: [
          IconButton(
            key: const Key('feed-roadmap-btn'),
            icon: const Icon(Icons.map_outlined),
            onPressed: () => context.go('/subjects/${widget.subjectId}/roadmap'),
            tooltip: 'Roadmap',
          ),
        ],
      ),
      body: feedAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.cloud_off_outlined, size: 56, color: colorScheme.error),
                const SizedBox(height: 12),
                Text(error.toString(), textAlign: TextAlign.center, key: const Key('feed-error-text')),
                const SizedBox(height: 16),
                FilledButton.icon(
                  key: const Key('feed-retry'),
                  onPressed: () => ref.invalidate(feedProvider(widget.subjectId)),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
        data: (feed) {
          if (feed.allTopicsCompleted) {
            return Center(
              key: const Key('feed-all-done'),
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.celebration, size: 64, color: colorScheme.primary),
                    const SizedBox(height: 12),
                    Text('All topics completed!', style: theme.textTheme.titleLarge),
                    const SizedBox(height: 8),
                    const Text('You have finished this subject. Great work!'),
                  ],
                ),
              ),
            );
          }
          if (feed.posts.isEmpty) {
            return Center(
              key: const Key('feed-empty'),
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const CircularProgressIndicator(),
                    const SizedBox(height: 12),
                    Text('Generating your personalized feed...', style: theme.textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text('This may take a few seconds. Pull to refresh.', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.outline)),
                  ],
                ),
              ),
            );
          }

          final topic = feed.topic;
          return RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(feedProvider(widget.subjectId));
              await ref.read(feedProvider(widget.subjectId).future);
              _prefetchTriggered = false;
            },
            child: CustomScrollView(
              controller: _scrollController,
              slivers: [
                SliverToBoxAdapter(
                  child: SubjectSwitcher(
                    selectedSubjectId: widget.subjectId,
                    onSelected: (newId) => context.go('/subjects/$newId/feed'),
                  ),
                ),
                SliverToBoxAdapter(
                  child: Container(
                    key: const Key('feed-topic-header'),
                    margin: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                    decoration: BoxDecoration(
                      color: colorScheme.primaryContainer.withValues(alpha: 0.4),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: colorScheme.primary.withValues(alpha: 0.2)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 36,
                          height: 36,
                          decoration: BoxDecoration(color: colorScheme.primary, shape: BoxShape.circle),
                          alignment: Alignment.center,
                          child: Text('${topic?.orderIndex ?? 1}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(topic?.title ?? 'Current topic', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                              const SizedBox(height: 2),
                              Text('${feed.postCount} bite${feed.postCount == 1 ? '' : 's'} • one topic at a time', style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.outline)),
                            ],
                          ),
                        ),
                        const Icon(Icons.auto_awesome, size: 20),
                      ],
                    ),
                  ),
                ),
                SliverList.separated(
                  itemCount: feed.posts.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final post = feed.posts[index];
                    return Padding(
                      padding: EdgeInsets.fromLTRB(16, index == 0 ? 4 : 0, 16, 0),
                      child: Card(
                        key: ValueKey('post-${post.id}'),
                        elevation: 0,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: BorderSide(color: colorScheme.outlineVariant)),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  CircleAvatar(radius: 14, backgroundColor: colorScheme.primary, child: Text('${index + 1}', style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700))),
                                  const SizedBox(width: 8),
                                  Text('Lesson ${index + 1} of ${feed.posts.length}', style: theme.textTheme.labelMedium?.copyWith(color: colorScheme.outline, fontWeight: FontWeight.w600)),
                                  const Spacer(),
                                  Text('${post.content.length} chars', style: theme.textTheme.labelSmall?.copyWith(color: colorScheme.outline)),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Text(post.content, key: ValueKey('post-content-${post.id}'), style: theme.textTheme.bodyMedium?.copyWith(height: 1.45)),
                              const SizedBox(height: 10),
                              Row(
                                children: [
                                  TextButton.icon(
                                    key: ValueKey('open-chat-${post.id}'),
                                    onPressed: () {
                                      final tid = feed.topic?.id ?? post.topicId;
                                      showChatSheet(context, subjectId: widget.subjectId, topicId: tid);
                                    },
                                    icon: const Icon(Icons.chat_bubble_outline, size: 16),
                                    label: const Text('Open Chat'),
                                  ),
                                  const Spacer(),
                                  if (post.orderIndex == 0) ...[
                                    Icon(Icons.lightbulb_outline, size: 14, color: colorScheme.outline),
                                    const SizedBox(width: 4),
                                    Text('JIT • personalized', style: theme.textTheme.labelSmall?.copyWith(color: colorScheme.outline)),
                                  ],
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (_completing) const LinearProgressIndicator(key: Key('complete-progress')),
                        const SizedBox(height: 8),
                        FilledButton.icon(
                          key: const Key('complete-topic'),
                          onPressed: _completing ? null : _complete,
                          icon: _completing ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.check_circle_outline),
                          label: Text(_completing ? 'Completing...' : 'Mark topic complete →'),
                        ),
                        const SizedBox(height: 8),
                        Text('Completing deletes this feed and loads the next topic (prefetched at 70%).', textAlign: TextAlign.center, style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.outline)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
