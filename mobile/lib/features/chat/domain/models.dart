class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.topicId,
    required this.role,
    required this.content,
    this.createdAt,
  });

  factory ChatMessage.fromJson(Map<Object?, Object?> json) => ChatMessage(
        id: json['id'] as int,
        topicId: json['topic_id'] as int,
        role: json['role'] as String,
        content: json['content'] as String,
        createdAt: json['created_at'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'topic_id': topicId,
        'role': role,
        'content': content,
        'created_at': createdAt,
      };

  final int id;
  final int topicId;
  final String role;
  final String content;
  final String? createdAt;

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';
}

class ChatResponse {
  const ChatResponse({required this.reply, required this.messages});

  factory ChatResponse.fromJson(Map<Object?, Object?> json) {
    final msgs = (json['messages'] as List<Object?>? ?? const [])
        .cast<Map<Object?, Object?>>()
        .map(ChatMessage.fromJson)
        .toList(growable: false);
    return ChatResponse(
      reply: json['reply'] as String? ?? '',
      messages: msgs,
    );
  }

  final String reply;
  final List<ChatMessage> messages;
}
