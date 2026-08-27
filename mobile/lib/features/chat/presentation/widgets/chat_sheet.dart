import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/chat_api_client.dart';
import '../providers.dart';

Future<void> showChatSheet(
  BuildContext context, {
  required String subjectId,
  required int topicId,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => ChatSheet(subjectId: subjectId, topicId: topicId),
  );
}

class ChatSheet extends ConsumerStatefulWidget {
  const ChatSheet({super.key, required this.subjectId, required this.topicId});

  final String subjectId;
  final int topicId;

  @override
  ConsumerState<ChatSheet> createState() => _ChatSheetState();
}

class _ChatSheetState extends ConsumerState<ChatSheet> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await ref.read(chatApiProvider).sendMessage(widget.subjectId, widget.topicId, text);
      _controller.clear();
      // Invalidate and reload history
      ref.invalidate(chatHistoryProvider((subjectId: widget.subjectId, topicId: widget.topicId)));
      // Wait a tick then scroll to bottom
      await Future<void>.delayed(const Duration(milliseconds: 200));
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent + 200,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    } on ChatApiException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  void _openFullScreen() {
    Navigator.of(context).pop();
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ChatScreen(subjectId: widget.subjectId, topicId: widget.topicId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final historyAsync = ref.watch(chatHistoryProvider((subjectId: widget.subjectId, topicId: widget.topicId)));
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;

    return Padding(
      padding: EdgeInsets.only(bottom: bottomInset),
      child: DraggableScrollableSheet(
        initialChildSize: 0.75,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        expand: false,
        builder: (context, scrollController) {
          // Use inner scroll for messages? Need separate controller for list
          return Column(
            children: [
              Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(top: 12, bottom: 8),
                decoration: BoxDecoration(color: colorScheme.outlineVariant, borderRadius: BorderRadius.circular(2)),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  children: [
                    Icon(Icons.chat_bubble_outline, color: colorScheme.primary),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text('Open Chat', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                    ),
                    IconButton(
                      key: const Key('chat-fullscreen-btn'),
                      icon: const Icon(Icons.open_in_full),
                      tooltip: 'Open full screen',
                      onPressed: _openFullScreen,
                    ),
                    IconButton(
                      key: const Key('chat-close-btn'),
                      icon: const Icon(Icons.close),
                      onPressed: () => Navigator.of(context).pop(),
                    ),
                  ],
                ),
              ),
              Divider(height: 1, color: colorScheme.outlineVariant),
              Expanded(
                child: historyAsync.when(
                  loading: () => const Center(child: CircularProgressIndicator(key: Key('chat-loading'))),
                  error: (error, _) {
                    String message = error.toString();
                    if (error is ChatApiException) {
                      if (error.statusCode == 502 || (error.statusCode != null && error.statusCode! >= 500 && error.statusCode! <= 504)) {
                        message = 'AI assistant is temporarily unavailable. Please retry.';
                      } else if (error.statusCode == 503) {
                        message = 'Service temporarily unavailable. Please check your connection and retry.';
                      } else {
                        message = error.message;
                      }
                    }
                    return Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.error_outline, size: 48, color: colorScheme.error),
                            const SizedBox(height: 12),
                            Text(message, textAlign: TextAlign.center, key: const Key('chat-error-text')),
                            const SizedBox(height: 16),
                            FilledButton.icon(
                              key: const Key('chat-retry'),
                              onPressed: () => ref.invalidate(chatHistoryProvider((subjectId: widget.subjectId, topicId: widget.topicId))),
                              icon: const Icon(Icons.refresh),
                              label: const Text('Retry'),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                  data: (messages) {
                    if (messages.isEmpty) {
                      return Center(
                        key: const Key('chat-empty'),
                        child: Padding(
                          padding: const EdgeInsets.all(32),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.chat_outlined, size: 48, color: colorScheme.outline),
                              const SizedBox(height: 12),
                              Text('No messages yet', style: theme.textTheme.titleMedium),
                              const SizedBox(height: 8),
                              Text('Ask anything about this topic — we use your profile + prerequisites for context.',
                                  textAlign: TextAlign.center, style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.outline)),
                            ],
                          ),
                        ),
                      );
                    }
                    return ListView.separated(
                      key: const Key('chat-history-list'),
                      controller: _scrollController,
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                      itemCount: messages.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 10),
                      itemBuilder: (context, index) {
                        final m = messages[index];
                        final isUser = m.isUser;
                        return Align(
                          alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                          child: Container(
                            key: ValueKey('chat-msg-${m.id}'),
                            constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                            decoration: BoxDecoration(
                              color: isUser ? colorScheme.primary : colorScheme.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(16).copyWith(
                                bottomRight: isUser ? const Radius.circular(4) : null,
                                bottomLeft: !isUser ? const Radius.circular(4) : null,
                              ),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(m.role.toUpperCase(),
                                    style: theme.textTheme.labelSmall?.copyWith(
                                      color: isUser ? colorScheme.onPrimary.withValues(alpha: 0.8) : colorScheme.outline,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: 0.5,
                                    )),
                                const SizedBox(height: 4),
                                Text(m.content,
                                    key: ValueKey('chat-msg-content-${m.id}'),
                                    style: theme.textTheme.bodyMedium?.copyWith(
                                      color: isUser ? colorScheme.onPrimary : colorScheme.onSurface,
                                      height: 1.4,
                                    )),
                              ],
                            ),
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
              if (_error != null)
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(color: colorScheme.errorContainer, borderRadius: BorderRadius.circular(8)),
                  child: Text(_error!, style: TextStyle(color: colorScheme.onErrorContainer), key: const Key('chat-send-error')),
                ),
              Container(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 16),
                decoration: BoxDecoration(
                  color: colorScheme.surface,
                  border: Border(top: BorderSide(color: colorScheme.outlineVariant)),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        key: const Key('chat-input'),
                        controller: _controller,
                        minLines: 1,
                        maxLines: 4,
                        textInputAction: TextInputAction.send,
                        onSubmitted: (_) => _send(),
                        decoration: InputDecoration(
                          hintText: 'Ask about this topic...',
                          filled: true,
                          fillColor: colorScheme.surfaceContainerHighest.withValues(alpha: 0.7),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    FilledButton(
                      key: const Key('chat-send-btn'),
                      onPressed: _sending ? null : _send,
                      style: FilledButton.styleFrom(shape: const CircleBorder(), padding: const EdgeInsets.all(14)),
                      child: _sending
                          ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.send, size: 20),
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

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key, required this.subjectId, required this.topicId});

  final String subjectId;
  final int topicId;

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await ref.read(chatApiProvider).sendMessage(widget.subjectId, widget.topicId, text);
      _controller.clear();
      ref.invalidate(chatHistoryProvider((subjectId: widget.subjectId, topicId: widget.topicId)));
      await Future<void>.delayed(const Duration(milliseconds: 200));
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent + 200,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    } on ChatApiException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final historyAsync = ref.watch(chatHistoryProvider((subjectId: widget.subjectId, topicId: widget.topicId)));
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Chat'), centerTitle: false),
      body: Column(
        children: [
          Expanded(
            child: historyAsync.when(
              loading: () => const Center(child: CircularProgressIndicator(key: Key('chat-screen-loading'))),
              error: (error, _) {
                String message = error.toString();
                if (error is ChatApiException) {
                  if (error.statusCode == 502 || (error.statusCode != null && error.statusCode! >= 500 && error.statusCode! <= 504)) {
                    message = 'AI assistant is temporarily unavailable. Please retry.';
                  } else if (error.statusCode == 503) {
                    message = 'Service temporarily unavailable. Please check your connection and retry.';
                  } else {
                    message = error.message;
                  }
                }
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.error_outline, size: 48, color: colorScheme.error),
                        const SizedBox(height: 12),
                        Text(message, textAlign: TextAlign.center, key: const Key('chat-screen-error')),
                        const SizedBox(height: 16),
                        FilledButton.icon(
                          key: const Key('chat-screen-retry'),
                          onPressed: () => ref.invalidate(chatHistoryProvider((subjectId: widget.subjectId, topicId: widget.topicId))),
                          icon: const Icon(Icons.refresh),
                          label: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                );
              },
              data: (messages) {
                if (messages.isEmpty) {
                  return Center(
                    key: const Key('chat-screen-empty'),
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.chat_outlined, size: 48, color: colorScheme.outline),
                          const SizedBox(height: 12),
                          Text('No messages yet', style: theme.textTheme.titleMedium),
                          const SizedBox(height: 8),
                          Text('Ask anything about this topic.', textAlign: TextAlign.center, style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.outline)),
                        ],
                      ),
                    ),
                  );
                }
                return ListView.separated(
                  key: const Key('chat-screen-list'),
                  controller: _scrollController,
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                  itemCount: messages.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final m = messages[index];
                    final isUser = m.isUser;
                    return Align(
                      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                      child: Container(
                        key: ValueKey('chat-screen-msg-${m.id}'),
                        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                          color: isUser ? colorScheme.primary : colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Text(m.content, style: theme.textTheme.bodyMedium?.copyWith(color: isUser ? colorScheme.onPrimary : colorScheme.onSurface)),
                      ),
                    );
                  },
                );
              },
            ),
          ),
          if (_error != null)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(color: colorScheme.errorContainer, borderRadius: BorderRadius.circular(8)),
              child: Text(_error!, style: TextStyle(color: colorScheme.onErrorContainer), key: const Key('chat-screen-send-error')),
            ),
          Container(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 16),
            decoration: BoxDecoration(border: Border(top: BorderSide(color: colorScheme.outlineVariant))),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('chat-screen-input'),
                    controller: _controller,
                    minLines: 1,
                    maxLines: 4,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _send(),
                    decoration: InputDecoration(
                      hintText: 'Ask about this topic...',
                      filled: true,
                      fillColor: colorScheme.surfaceContainerHighest.withValues(alpha: 0.7),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  key: const Key('chat-screen-send'),
                  onPressed: _sending ? null : _send,
                  style: FilledButton.styleFrom(shape: const CircleBorder(), padding: const EdgeInsets.all(14)),
                  child: _sending
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Icon(Icons.send, size: 20),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
