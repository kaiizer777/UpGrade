"use client";

import * as React from "react";
import {
  AlertCircle,
  Bot,
  HelpCircle,
  Lightbulb,
  MessageSquare,
  RefreshCw,
  Sparkles,
  User,
  X,
} from "lucide-react";
import type { FeedPostRead } from "@/lib/types";
import { useAutoScroll } from "@/hooks/use-auto-scroll";
import { useChat } from "@/hooks/use-chat";
import { ChatInput } from "@/components/chat-input";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface ChatPanelProps {
  subjectId: string;
  topicId: number;
  topicTitle?: string;
  initialPost?: FeedPostRead | null;
  onClose?: () => void;
  className?: string;
}

const STARTER_QUESTIONS = [
  "Can you explain this concept in simpler terms?",
  "Could you provide a real-world code example?",
  "What are the common pitfalls or edge cases here?",
  "Why do we approach this problem this way?",
];

export function ChatPanel({
  subjectId,
  topicId,
  topicTitle,
  initialPost,
  onClose,
  className,
}: ChatPanelProps) {
  const {
    messages,
    isLoading,
    isSending,
    error,
    sendMessage,
    reload,
    clearError,
  } = useChat({
    subjectId,
    topicId,
    enabled: Boolean(subjectId && topicId),
  });

  const { scrollRef, bottomRef } = useAutoScroll([messages, isSending]);

  const handleSuggestionClick = (prompt: string) => {
    void sendMessage(prompt);
  };

  return (
    <div className={cn("flex h-full w-full flex-col overflow-hidden bg-background", className)}>
      {/* Optional Context Box for specific feed post reference */}
      {initialPost && (
        <div className="mx-4 mt-3 shrink-0 rounded-lg border border-border/80 bg-muted/40 p-3 text-xs shadow-xs">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 font-semibold text-foreground">
              <Sparkles className="size-3.5 text-amber-500" aria-hidden="true" />
              <span>Discussing Post #{initialPost.order_index + 1}</span>
            </div>
            <span className="text-[10px] text-muted-foreground font-mono">
              Topic #{initialPost.topic_id}
            </span>
          </div>
          <p className="mt-1 line-clamp-2 text-muted-foreground leading-relaxed">
            {initialPost.content}
          </p>
        </div>
      )}

      {/* Message List Scroll Area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
        role="region"
        aria-label="Discussion thread"
        aria-live="polite"
      >
        {/* Initial Loading Skeletons */}
        {isLoading && messages.length === 0 ? (
          <div className="space-y-4 py-2" aria-label="Loading conversation history">
            <div className="flex items-start gap-3 mr-auto max-w-[85%]">
              <Skeleton className="size-7 rounded-full shrink-0" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-16 w-full rounded-xl" />
              </div>
            </div>
            <div className="flex items-start gap-3 ml-auto max-w-[80%] flex-row-reverse">
              <Skeleton className="size-7 rounded-full shrink-0" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-20 ml-auto" />
                <Skeleton className="h-12 w-full rounded-xl" />
              </div>
            </div>
            <div className="flex items-start gap-3 mr-auto max-w-[85%]">
              <Skeleton className="size-7 rounded-full shrink-0" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-20 w-full rounded-xl" />
              </div>
            </div>
          </div>
        ) : messages.length === 0 ? (
          /* Empty State */
          <div className="flex min-h-[300px] flex-col items-center justify-center text-center p-4">
            <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary mb-3">
              <MessageSquare className="size-6" aria-hidden="true" />
            </div>
            <h3 className="font-heading text-base font-semibold text-foreground">
              Have doubts about {topicTitle || "this topic"}?
            </h3>
            <p className="mt-1 max-w-sm text-xs text-muted-foreground leading-relaxed">
              Ask anything to deepen your understanding. UpGrade AI is ready to clarify concepts,
              walk through code, or test your knowledge.
            </p>

            {/* Quick Starter Suggestions */}
            <div className="mt-6 flex w-full max-w-md flex-col gap-2">
              <span className="flex items-center justify-center gap-1 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                <Lightbulb className="size-3 text-amber-500" aria-hidden="true" />
                Quick suggestions
              </span>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {STARTER_QUESTIONS.map((suggestion, idx) => (
                  <Button
                    key={idx}
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isSending}
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="h-auto justify-start p-2.5 text-left text-xs whitespace-normal leading-snug border-border/80 hover:border-primary/50 hover:bg-muted/50"
                  >
                    <HelpCircle className="mr-1.5 size-3.5 shrink-0 text-primary" aria-hidden="true" />
                    <span>{suggestion}</span>
                  </Button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Messages Stream */
          messages.map((msg, index) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id ?? `msg-${index}`}
                className={cn(
                  "flex items-start gap-2.5",
                  isUser ? "ml-auto max-w-[88%] flex-row-reverse" : "mr-auto max-w-[92%]"
                )}
              >
                {/* Avatar Icon */}
                <div
                  className={cn(
                    "flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold select-none",
                    isUser
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted border border-border text-foreground"
                  )}
                  aria-hidden="true"
                >
                  {isUser ? <User className="size-3.5" /> : <Bot className="size-3.5 text-primary" />}
                </div>

                {/* Message Bubble */}
                <div className="flex flex-col gap-1">
                  <div
                    className={cn(
                      "flex items-center gap-1.5 text-[10px] text-muted-foreground",
                      isUser && "justify-end"
                    )}
                  >
                    <span className="font-medium">
                      {isUser ? "You" : "UpGrade AI"}
                    </span>
                    {msg.created_at && (
                      <span>
                        •{" "}
                        {new Date(msg.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    )}
                  </div>

                  <div
                    className={cn(
                      "rounded-2xl px-4 py-2.5 text-xs sm:text-sm leading-relaxed shadow-2xs",
                      isUser
                        ? "bg-primary text-primary-foreground rounded-tr-xs"
                        : "bg-card text-card-foreground border border-border/80 rounded-tl-xs"
                    )}
                  >
                    {isUser ? (
                      <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    ) : (
                      <Markdown content={msg.content} />
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}

        {/* Assistant Skeleton while AI is streaming/generating */}
        {isSending && (
          <div className="flex items-start gap-2.5 mr-auto max-w-[90%] animate-in fade-in-0 duration-200">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted border border-border text-primary">
              <Bot className="size-3.5" />
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] font-medium text-muted-foreground">UpGrade AI</span>
              <div className="flex items-center gap-2 rounded-2xl rounded-tl-xs border border-border/80 bg-card px-4 py-3 text-xs text-muted-foreground shadow-2xs">
                <span className="flex gap-1">
                  <span className="size-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.3s]" />
                  <span className="size-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.15s]" />
                  <span className="size-1.5 rounded-full bg-primary animate-bounce" />
                </span>
                <span className="ml-1 text-xs">Analyzing topic context & thinking...</span>
              </div>
            </div>
          </div>
        )}

        {/* Inline Error State with Retry Button */}
        {error && (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive"
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="size-4 shrink-0 text-destructive" aria-hidden="true" />
              <span>{error.message || "Failed to reach AI service"}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Button
                type="button"
                variant="outline"
                size="xs"
                onClick={() => reload()}
                className="h-7 gap-1.5 border-destructive/30 bg-background text-foreground hover:bg-destructive/10"
              >
                <RefreshCw className="size-3" />
                <span>Retry</span>
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                onClick={() => clearError()}
                className="size-7 text-muted-foreground hover:text-foreground"
                aria-label="Dismiss error banner"
              >
                <X className="size-3" />
              </Button>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Chat Input Bar */}
      <div className="shrink-0 border-t border-border/80 bg-background/95 p-3">
        <ChatInput
          onSend={sendMessage}
          disabled={isLoading}
          isSending={isSending}
          placeholder="Ask a question or clarify doubts..."
          onEscape={onClose}
        />
      </div>
    </div>
  );
}
