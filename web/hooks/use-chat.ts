"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ApiError, getChat, postChat } from "@/lib/api";
import type { ChatMessageRead } from "@/lib/types";

export interface UseChatOptions {
  subjectId: string;
  topicId: number;
  enabled?: boolean;
}

export interface UseChatReturn {
  messages: ChatMessageRead[];
  isLoading: boolean;
  isSending: boolean;
  error: ApiError | Error | null;
  sendMessage: (content: string) => Promise<void>;
  reload: () => Promise<void>;
  clearError: () => void;
}

/**
 * Hook for managing topic-scoped doubts chat.
 * Handles optimistic updates, authoritative server response sync, and 502/503 AI error retries.
 */
export function useChat({
  subjectId,
  topicId,
  enabled = true,
}: UseChatOptions): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessageRead[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(Boolean(enabled && subjectId && topicId));
  const [isSending, setIsSending] = useState<boolean>(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  // Load chat history when subjectId or topicId changes
  useEffect(() => {
    let isMounted = true;

    if (!enabled || !subjectId || !topicId) {
      return;
    }

    getChat(subjectId, topicId)
      .then((data) => {
        if (isMounted) {
          // Deduplicate messages by id while preserving ordering
          const uniqueMessages = Array.from(
            new Map((data.messages || []).map((m) => [m.id, m])).values()
          );
          setMessages(uniqueMessages);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          const errorObj =
            err instanceof Error ? err : new Error("Failed to load chat history");
          setError(errorObj);
          setIsLoading(false);

          const status = err instanceof ApiError ? err.status : undefined;
          if (status === 502 || status === 503) {
            toast.error("AI service temporarily unavailable (503)", {
              description: "Could not retrieve discussion history.",
            });
          }
        }
      });

    return () => {
      isMounted = false;
    };
  }, [enabled, subjectId, topicId]);

  // Manual reload helper
  const reload = useCallback(async () => {
    if (!enabled || !subjectId || !topicId) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await getChat(subjectId, topicId);
      const uniqueMessages = Array.from(
        new Map((data.messages || []).map((m) => [m.id, m])).values()
      );
      setMessages(uniqueMessages);
    } catch (err) {
      const errorObj =
        err instanceof Error ? err : new Error("Failed to load chat history");
      setError(errorObj);
      toast.error("Failed to refresh discussion", { description: errorObj.message });
    } finally {
      setIsLoading(false);
    }
  }, [enabled, subjectId, topicId]);

  // Send a new doubt turn to the backend
  const sendMessage = useCallback(
    async (rawContent: string) => {
      const content = rawContent.trim();
      if (!content || isSending || !subjectId || !topicId) return;

      const tempId = -Date.now();
      const optimisticUserMsg: ChatMessageRead = {
        id: tempId,
        topic_id: topicId,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };

      // 1. Optimistically append user message
      setMessages((prev) => [...prev, optimisticUserMsg]);
      setIsSending(true);
      setError(null);

      try {
        // 2. Await direct FastAPI call (wait for authoritative response, no client hallucination)
        const res = await postChat(subjectId, topicId, content);

        // 3. Deduplicate and synchronize authoritative full message stream from server
        const deduplicated = Array.from(
          new Map((res.messages || []).map((m) => [m.id, m])).values()
        );
        setMessages(deduplicated);
      } catch (err) {
        // 4. On failure, remove optimistic user message and handle 502/503 or generic errors
        setMessages((prev) => prev.filter((m) => m.id !== tempId));

        const errorObj =
          err instanceof Error ? err : new Error("Failed to send message");
        setError(errorObj);

        const status = err instanceof ApiError ? err.status : undefined;
        if (status === 502 || status === 503) {
          toast.error("AI provider timeout (502/503)", {
            description: "The AI service is experiencing heavy load. Please try again.",
          });
        } else {
          toast.error("Failed to send doubt", {
            description: errorObj.message,
          });
        }
      } finally {
        setIsSending(false);
      }
    },
    [isSending, subjectId, topicId]
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    isSending,
    error,
    sendMessage,
    reload,
    clearError,
  };
}
