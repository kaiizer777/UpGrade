import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:upgrade/features/chat/data/chat_api_client.dart';
import 'package:upgrade/features/chat/domain/models.dart';
import 'package:upgrade/features/chat/presentation/providers.dart';
import 'package:upgrade/features/chat/presentation/widgets/chat_sheet.dart';

class FakeChatApiClient implements ChatApiClient {
  FakeChatApiClient({List<ChatMessage>? initial, this.sendError, this.getError}) : _messages = initial ?? [];

  List<ChatMessage> _messages;
  Object? sendError;
  Object? getError;
  int sendCalls = 0;
  int getCalls = 0;

  @override
  String get baseUrl => 'fake://api';

  @override
  Future<List<ChatMessage>> getHistory(String subjectId, int topicId) async {
    getCalls++;
    if (getError != null) throw getError!;
    return List<ChatMessage>.from(_messages);
  }

  @override
  Future<ChatResponse> sendMessage(String subjectId, int topicId, String message) async {
    sendCalls++;
    if (sendError != null) throw sendError!;
    final userMsg = ChatMessage(id: _messages.length + 1, topicId: topicId, role: 'user', content: message);
    final aiMsg = ChatMessage(id: _messages.length + 2, topicId: topicId, role: 'assistant', content: 'Reply to: $message');
    _messages = [..._messages, userMsg, aiMsg];
    return ChatResponse(reply: aiMsg.content, messages: List<ChatMessage>.from(_messages));
  }

  @override
  void close() {}
}

Future<void> pumpChatSheet(
  WidgetTester tester,
  FakeChatApiClient api, {
  String subjectId = 'subject-1',
  int topicId = 1,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [chatApiProvider.overrideWithValue(api)],
      child: MaterialApp(home: Scaffold(body: ChatSheet(subjectId: subjectId, topicId: topicId))),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('empty history shows placeholder', (tester) async {
    final api = FakeChatApiClient(initial: []);
    await pumpChatSheet(tester, api);
    expect(find.byKey(const Key('chat-empty')), findsOneWidget);
    expect(find.text('No messages yet'), findsOneWidget);
  });

  testWidgets('populated history shows messages', (tester) async {
    final api = FakeChatApiClient(initial: [
      const ChatMessage(id: 1, topicId: 1, role: 'user', content: 'hi'),
      const ChatMessage(id: 2, topicId: 1, role: 'assistant', content: 'hello there'),
    ]);
    await pumpChatSheet(tester, api);
    expect(find.byKey(const Key('chat-history-list')), findsOneWidget);
    expect(find.text('hi'), findsOneWidget);
    expect(find.text('hello there'), findsOneWidget);
    expect(find.byKey(const ValueKey('chat-msg-1')), findsOneWidget);
    expect(find.byKey(const ValueKey('chat-msg-2')), findsOneWidget);
  });

  testWidgets('loading shows spinner', (tester) async {
    final api = FakeChatApiClient();
    // Make getHistory hang by using a completer? Simpler: override provider to async delayed
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          chatHistoryProvider.overrideWith((ref, args) async {
            await Future<void>.delayed(const Duration(milliseconds: 300));
            return <ChatMessage>[];
          }),
          chatApiProvider.overrideWithValue(api),
        ],
        child: MaterialApp(home: Scaffold(body: ChatSheet(subjectId: 'subject-1', topicId: 1))),
      ),
    );
    expect(find.byKey(const Key('chat-loading')), findsOneWidget);
    await tester.pumpAndSettle();
  });

  testWidgets('error shows retry', (tester) async {
    final api = FakeChatApiClient(getError: const ChatApiException('Network error'));
    await pumpChatSheet(tester, api);
    expect(find.byKey(const Key('chat-error-text')), findsOneWidget);
    expect(find.byKey(const Key('chat-retry')), findsOneWidget);
  });

  testWidgets('send message persists and updates list', (tester) async {
    final api = FakeChatApiClient(initial: []);
    await pumpChatSheet(tester, api);

    // Type and send
    await tester.enterText(find.byKey(const Key('chat-input')), 'explain recursion');
    await tester.tap(find.byKey(const Key('chat-send-btn')));
    await tester.pumpAndSettle();

    expect(api.sendCalls, 1);
    expect(find.text('explain recursion'), findsOneWidget);
    expect(find.text('Reply to: explain recursion'), findsOneWidget);
  });

  testWidgets('ChatScreen empty and send', (tester) async {
    final api = FakeChatApiClient(initial: []);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [chatApiProvider.overrideWithValue(api)],
        child: MaterialApp(home: ChatScreen(subjectId: 'subject-1', topicId: 1)),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('chat-screen-empty')), findsOneWidget);
    await tester.enterText(find.byKey(const Key('chat-screen-input')), 'hello');
    await tester.tap(find.byKey(const Key('chat-screen-send')));
    await tester.pumpAndSettle();
    expect(api.sendCalls, 1);
    expect(find.text('hello'), findsOneWidget);
  });
}
