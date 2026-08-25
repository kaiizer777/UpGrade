import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/api_client.dart';
import '../providers.dart';

/// `/subjects/:id/onboarding` — Twitter-style chat with the onboarding AI.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key, required this.subjectId});

  final String subjectId;

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _textController = TextEditingController();

  OnboardingController get _controller =>
      ref.read(onboardingControllerProvider(widget.subjectId).notifier);

  void _submit() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;
    _textController.clear();
    FocusManager.instance.primaryFocus?.unfocus();
    _controller.send(text);
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final asyncView = ref.watch(onboardingControllerProvider(widget.subjectId));

    return Scaffold(
      appBar: AppBar(title: const Text('Set up your plan')),
      body: SafeArea(
        child: asyncView.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => _SeedErrorView(
            message: error is ApiException ? error.message : error.toString(),
            onRetry: () =>
                ref.invalidate(onboardingControllerProvider(widget.subjectId)),
          ),
          data: (view) => Column(
            children: [
              _ProgressHeader(view: view),
              if (view.isReady) const _ReadyBanner(key: Key('ready-banner')),
              Expanded(
                child: view.entries.isEmpty
                    ? const _EmptyTranscript()
                    : _ChatList(
                        key: const Key('onboarding-list'),
                        entries: view.entries,
                        onRetry: (entryId) => _controller.resendFailed(entryId),
                      ),
              ),
              _Composer(
                key: const Key('onboarding-composer'),
                controller: _textController,
                enabled: !view.isLoading && !view.isReady,
                disabledNotice:
                    view.isReady ? 'Onboarding is complete.' : null,
                onSubmit: _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// Header

class _ProgressHeader extends StatelessWidget {
  const _ProgressHeader({required this.view});

  final OnboardingViewState view;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final score = math.max(0, math.min(100, view.completeness?.score ?? 0));
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          LinearProgressIndicator(
            key: const Key('onboarding-progress-bar'),
            value: score / 100,
            minHeight: 6,
            borderRadius: BorderRadius.circular(3),
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Q ${view.questionsAsked}/${view.maxQuestions}',
                key: const Key('onboarding-question-count'),
                style: theme.textTheme.labelMedium
                    ?.copyWith(color: theme.colorScheme.outline),
              ),
              Text(
                '$score% complete',
                key: const Key('onboarding-progress-caption'),
                style: theme.textTheme.labelMedium
                    ?.copyWith(color: theme.colorScheme.outline),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ReadyBanner extends StatelessWidget {
  const _ReadyBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 0),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(Icons.celebration_outlined, color: colorScheme.onPrimaryContainer),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              "You're all set! Building your personalized plan…",
              style: TextStyle(
                color: colorScheme.onPrimaryContainer,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// Chat list & bubbles

class _ChatList extends StatelessWidget {
  const _ChatList({
    super.key,
    required this.entries,
    required this.onRetry,
  });

  final List<OnboardingChatEntry> entries;
  final ValueChanged<int> onRetry;

  @override
  Widget build(BuildContext context) {
    // reverse:true pins index 0 to the bottom, so freshly appended entries
    // appear in place and the viewport stays anchored on the latest message.
    return ListView.builder(
      reverse: true,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      itemCount: entries.length,
      itemBuilder: (context, index) {
        final entry = entries[entries.length - 1 - index];
        if (entry.isTyping) {
          return const _TypingBubble(key: Key('typing-indicator'));
        }
        if (entry.isError) return _ErrorBubble(entry: entry, onRetry: onRetry);
        return _MessageBubble(entry: entry);
      },
    );
  }
}

class _EmptyTranscript extends StatelessWidget {
  const _EmptyTranscript();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(
          'Say hello — UpGrade will ask a few questions to tailor your plan.',
          textAlign: TextAlign.center,
          style: theme.textTheme.bodyMedium
              ?.copyWith(color: theme.colorScheme.outline),
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.entry});

  final OnboardingChatEntry entry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final isUser = entry.role == ChatRole.user;
    final timestamp =
        '${entry.timestamp.hour.toString().padLeft(2, '0')}:${entry.timestamp.minute.toString().padLeft(2, '0')}';

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        key: ValueKey('chat-entry-${entry.id}'),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: const BoxConstraints(maxWidth: 300),
        decoration: BoxDecoration(
          color:
              isUser ? colorScheme.primary : colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(isUser ? 18 : 4), // small tail side
            bottomRight: Radius.circular(isUser ? 4 : 18),
          ),
          boxShadow: [
            BoxShadow(
              color: colorScheme.shadow.withValues(alpha: 0.08),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment:
              isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            Text(
              entry.text,
              style: theme.textTheme.bodyLarge?.copyWith(
                color: isUser ? colorScheme.onPrimary : colorScheme.onSurface,
                height: 1.35,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              timestamp,
              style: theme.textTheme.labelSmall?.copyWith(
                color: (isUser
                        ? colorScheme.onPrimary
                        : colorScheme.onSurfaceVariant)
                    .withValues(alpha: 0.7),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TypingBubble extends StatefulWidget {
  const _TypingBubble({super.key});

  @override
  State<_TypingBubble> createState() => _TypingBubbleState();
}

class _TypingBubbleState extends State<_TypingBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController _wave = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat();

  @override
  void dispose() {
    _wave.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    Widget dot(int position) => FadeTransition(
          opacity: Tween<double>(begin: 0.25, end: 0.9).animate(
            CurvedAnimation(
              parent: _wave,
              curve: Interval(
                position * 0.2,
                position * 0.2 + 0.5,
                curve: Curves.easeInOut,
              ),
            ),
          ),
          child: Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: theme.colorScheme.primary,
              shape: BoxShape.circle,
            ),
          ),
        );

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(18),
            topRight: Radius.circular(18),
            bottomLeft: Radius.circular(4),
            bottomRight: Radius.circular(18),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            dot(0),
            const SizedBox(width: 5),
            dot(1),
            const SizedBox(width: 5),
            dot(2),
          ],
        ),
      ),
    );
  }
}

class _ErrorBubble extends StatelessWidget {
  const _ErrorBubble({required this.entry, required this.onRetry});

  final OnboardingChatEntry entry;
  final ValueChanged<int> onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        key: ValueKey('chat-error-${entry.id}'),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: const BoxConstraints(maxWidth: 300),
        decoration: BoxDecoration(
          color: colorScheme.errorContainer,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(18),
            topRight: Radius.circular(18),
            bottomLeft: Radius.circular(4),
            bottomRight: Radius.circular(18),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.warning_amber_rounded,
                    size: 18, color: colorScheme.onErrorContainer),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'Message not sent',
                    style: theme.textTheme.labelLarge
                        ?.copyWith(color: colorScheme.onErrorContainer),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              entry.text,
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: colorScheme.onErrorContainer),
            ),
            if (entry.failedContent != null)
              TextButton.icon(
                key: ValueKey('chat-retry-${entry.id}'),
                onPressed: () => onRetry(entry.id),
                icon: Icon(Icons.refresh,
                    size: 16, color: colorScheme.onErrorContainer),
                label: Text('Retry',
                    style: TextStyle(color: colorScheme.onErrorContainer)),
                style: TextButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  padding: const EdgeInsets.only(left: 0, right: 8),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// Composer

class _Composer extends StatefulWidget {
  const _Composer({
    super.key,
    required this.controller,
    required this.enabled,
    required this.disabledNotice,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final bool enabled;
  final String? disabledNotice;
  final VoidCallback onSubmit;

  @override
  State<_Composer> createState() => _ComposerState();
}

class _ComposerState extends State<_Composer> {
  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Material(
      elevation: 6,
      color: colorScheme.surface,
      child: Padding(
        padding: EdgeInsets.only(
          left: 12,
          right: 12,
          top: 8,
          bottom: 8 + MediaQuery.paddingOf(context).bottom,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                key: const Key('onboarding-input'),
                controller: widget.controller,
                enabled: widget.enabled,
                minLines: 1,
                maxLines: 4,
                keyboardType: TextInputType.multiline,
                textInputAction: TextInputAction.newline,
                decoration: InputDecoration(
                  hintText: widget.disabledNotice ?? 'Type your answer…',
                  filled: true,
                  contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            // Rebuild only the button as text changes so the rest of the bar
            // stays still.
            ValueListenableBuilder<TextEditingValue>(
              valueListenable: widget.controller,
              builder: (context, value, _) {
                final canSend =
                    widget.enabled && value.text.trim().isNotEmpty;
                return IconButton.filled(
                  key: const Key('onboarding-send'),
                  onPressed: canSend ? widget.onSubmit : null,
                  icon: const Icon(Icons.send_rounded, size: 20),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  void didUpdateWidget(covariant _Composer oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Enabled-state flips (loading/ready) must re-evaluate the send button
    // even when text hasn't changed.
    if (oldWidget.enabled != widget.enabled) setState(() {});
  }
}

class _SeedErrorView extends StatelessWidget {
  const _SeedErrorView({required this.message, required this.onRetry});

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
              key: const Key('onboarding-retry-seed'),
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
