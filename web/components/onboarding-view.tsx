"use client";

import * as React from "react";
import { useCallback, useRef, useState } from "react";
import {
  AlertCircle,
  HelpCircle,
  Loader2,
  RefreshCw,
  Send,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import {
  ApiError,
  getOnboardingState,
  postOnboardingMessage,
} from "@/lib/api";
import type {
  CompletenessRead,
  OnboardingStateRead,
  SubjectProfileSlotRead,
} from "@/lib/types";
import { useAutoScroll } from "@/hooks/use-auto-scroll";
import { ChatBubble, ChatBubbleLoading } from "@/components/chat-bubble";
import { OnboardingComplete } from "@/components/onboarding-complete";
import { OnboardingProgress } from "@/components/onboarding-progress";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface OnboardingChatTurn {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
  error?: string | null;
  failedContent?: string;
}

export interface OnboardingViewProps {
  subjectId: string;
  subjectTitle: string;
  subjectDescription?: string | null;
  initialState?: OnboardingStateRead | null;
  className?: string;
}

const STARTER_GOALS = [
  "I want to master foundational concepts from scratch.",
  "I need to prepare for technical interviews & problem-solving.",
  "I want to build real-world production projects.",
  "I have intermediate knowledge and want advanced deep-dives.",
];

export function OnboardingView({
  subjectId,
  subjectTitle,
  subjectDescription,
  initialState,
  className,
}: OnboardingViewProps) {
  // 1. Core State
  const [status, setStatus] = useState<string>(initialState?.status || "onboarding");
  const [questionsAsked, setQuestionsAsked] = useState<number>(
    initialState?.questions_asked ?? 0
  );
  const [maxQuestions, setMaxQuestions] = useState<number>(
    initialState?.max_questions ?? 10
  );
  const [completeness, setCompleteness] = useState<CompletenessRead>(
    initialState?.completeness ?? { score: 0, filled_slots: [], missing_slots: [] }
  );
  const [profile, setProfile] = useState<SubjectProfileSlotRead | null>(
    initialState?.profile ?? null
  );

  // 2. Chat Messages State
  const [messages, setMessages] = useState<OnboardingChatTurn[]>(() => {
    const turns: OnboardingChatTurn[] = [];

    if (initialState?.answers && initialState.answers.length > 0) {
      initialState.answers.forEach((ans, idx) => {
        turns.push({
          id: `q-${idx}`,
          role: "assistant",
          content: ans.question,
          created_at: ans.created_at,
        });
        turns.push({
          id: `a-${idx}`,
          role: "user",
          content: ans.answer,
          created_at: ans.created_at,
        });
      });
    } else {
      // Initial Welcome Message
      turns.push({
        id: "welcome-coach",
        role: "assistant",
        content: `Hey twin! I'm your UpGrade onboarding coach. Let's tailor your curriculum for **${subjectTitle}**${
          subjectDescription ? ` (${subjectDescription})` : ""
        }.\n\nTo get started: **What is your primary goal, or what do you hope to achieve with this subject?**`,
        created_at: new Date().toISOString(),
      });
    }

    return turns;
  });

  const [inputVal, setInputVal] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [networkError, setNetworkError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const isReady = status === "ready" || profile?.status === "ready";

  // 3. Auto Scroll Hook
  const { scrollRef, bottomRef } = useAutoScroll<HTMLDivElement>(
    [messages, isPending],
    { threshold: 80 }
  );

  // Adjust textarea dynamic height
  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 40), 140);
    textarea.style.height = `${newHeight}px`;
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputVal(e.target.value);
    adjustHeight();
  };

  // 4. Send Message Handler
  const handleSendMessage = useCallback(
    async (rawContent: string, retryId?: number | string) => {
      const content = rawContent.trim();
      if (!content || isPending || isReady) return;

      setNetworkError(null);
      const tempId = retryId ?? -Date.now();

      if (!retryId) {
        // Append optimistic message
        setMessages((prev) => [
          ...prev,
          {
            id: tempId,
            role: "user",
            content,
            created_at: new Date().toISOString(),
          },
        ]);
        setInputVal("");
        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
        }
      } else {
        // Clear error flag on the retried message
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === retryId ? { ...msg, error: null, failedContent: undefined } : msg
          )
        );
      }

      setIsPending(true);

      try {
        const res = await postOnboardingMessage(subjectId, content);

        // Update conversation turns
        setMessages((prev) => {
          const filtered = prev.filter((m) => m.id !== tempId);
          return [
            ...filtered,
            {
              id: `user-${Date.now()}`,
              role: "user",
              content,
              created_at: new Date().toISOString(),
            },
            {
              id: `ai-${Date.now()}`,
              role: "assistant",
              content: res.reply,
              created_at: new Date().toISOString(),
            },
          ];
        });

        // Sync fresh state from turn response
        setStatus(res.status);
        setQuestionsAsked(res.questions_asked);
        setMaxQuestions(res.max_questions);
        setCompleteness(res.completeness);
        if (res.profile) {
          setProfile(res.profile);
        }

        if (res.status === "ready") {
          toast.success("Profile complete!", {
            description: "All dimensions captured. Ready to generate roadmap.",
          });
        }
      } catch (err: unknown) {
        console.error("[OnboardingView] Message send failed:", err);
        const status = (err as { status?: number })?.status;
        const is502or503 = status === 502 || status === 503;
        const errorMsg =
          err instanceof ApiError
            ? err.message
            : is502or503
            ? "AI service is temporarily starting up or busy (502/503)."
            : "Failed to send message. Please retry.";

        setNetworkError(errorMsg);

        // Mark optimistic message with error and keep failedContent for retry
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempId
              ? {
                  ...msg,
                  error: "Failed to send",
                  failedContent: content,
                }
              : msg
          )
        );

        toast.error(is502or503 ? "AI Service Unavailable (502/503)" : "Message Failed", {
          description: errorMsg,
        });
      } finally {
        setIsPending(false);
      }
    },
    [isPending, isReady, subjectId]
  );

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    void handleSendMessage(inputVal);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    }
  };

  const handleRetryState = async () => {
    try {
      const freshState = await getOnboardingState(subjectId);
      setStatus(freshState.status);
      setQuestionsAsked(freshState.questions_asked);
      setMaxQuestions(freshState.max_questions);
      setCompleteness(freshState.completeness);
      setProfile(freshState.profile);
      setNetworkError(null);
      toast.success("Synced onboarding state.");
    } catch {
      toast.error("Could not sync state. Please refresh.");
    }
  };

  const isSubmitDisabled = isPending || isReady || !inputVal.trim();

  return (
    <div className={cn("flex flex-col gap-4 w-full max-w-4xl mx-auto", className)}>
      {/* 1. Progress Header Card */}
      <OnboardingProgress
        questionsAsked={questionsAsked}
        maxQuestions={maxQuestions}
        completeness={completeness}
        profile={profile}
        status={status}
      />

      {/* 2. When Ready: Completion Card */}
      {isReady ? (
        <OnboardingComplete
          subjectId={subjectId}
          subjectTitle={subjectTitle}
          profile={profile}
        />
      ) : null}

      {/* 3. Main Chat Stream Container */}
      <div className="flex flex-col rounded-xl border border-border/80 bg-background shadow-xs overflow-hidden min-h-[460px] max-h-[640px]">
        {/* Chat Messages List */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 space-y-4"
          role="region"
          aria-label="Onboarding interview thread"
          aria-live="polite"
        >
          {messages.map((turn) => (
            <ChatBubble
              key={turn.id}
              role={turn.role}
              content={turn.content}
              timestamp={turn.created_at ?? undefined}
              error={turn.error}
              onRetry={
                turn.failedContent
                  ? () => void handleSendMessage(turn.failedContent!, turn.id)
                  : undefined
              }
            />
          ))}

          {/* Pending AI Loading indicator */}
          {isPending && <ChatBubbleLoading label="Synthesizing answers & crafting next question..." />}

          {/* Starter Suggestions on first turn */}
          {messages.length === 1 && !isPending && !isReady && (
            <div className="pt-2 animate-in fade-in-0 duration-300">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                <Sparkles className="size-3.5 text-amber-500" />
                <span>Quick Starter Responses</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {STARTER_GOALS.map((suggestion, idx) => (
                  <Button
                    key={idx}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void handleSendMessage(suggestion)}
                    className="h-auto justify-start p-2.5 text-left text-xs whitespace-normal leading-snug border-border/80 hover:border-primary/50 hover:bg-muted/50"
                  >
                    <HelpCircle className="mr-1.5 size-3.5 shrink-0 text-primary" />
                    <span>{suggestion}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Inline Network Error alert */}
          {networkError && (
            <div
              role="alert"
              className="flex items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive animate-in fade-in-0 duration-200"
            >
              <div className="flex items-center gap-2">
                <AlertCircle className="size-4 shrink-0 text-destructive" />
                <span>{networkError}</span>
              </div>
              <Button
                type="button"
                variant="outline"
                size="xs"
                onClick={handleRetryState}
                className="h-7 gap-1.5 border-destructive/30 bg-background text-foreground hover:bg-destructive/10 shrink-0"
              >
                <RefreshCw className="size-3" />
                <span>Sync State</span>
              </Button>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* 4. Chat Composer Bar */}
        <div className="border-t border-border/80 bg-muted/20 p-3">
          {isReady ? (
            <div className="text-center py-2 text-xs font-medium text-muted-foreground">
              Onboarding interview completed. You can now proceed to your roadmap above.
            </div>
          ) : (
            <form
              onSubmit={handleSubmit}
              className="relative flex items-end gap-2 rounded-xl border border-border/80 bg-background p-2 shadow-xs transition-colors focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-ring/30"
            >
              <textarea
                ref={textareaRef}
                rows={1}
                value={inputVal}
                onChange={handleTextChange}
                onKeyDown={handleKeyDown}
                placeholder="Type your response... (Enter to send, Shift+Enter for newline)"
                disabled={isPending || isReady}
                maxLength={280}
                aria-label="Onboarding message input"
                className="max-h-[140px] min-h-[40px] flex-1 resize-none bg-transparent px-2.5 py-2 text-xs sm:text-sm text-foreground placeholder:text-muted-foreground focus:outline-hidden disabled:cursor-not-allowed disabled:opacity-50"
              />

              <div className="flex shrink-0 items-center gap-2 pb-0.5">
                <span className="text-[10px] text-muted-foreground/80 font-mono hidden sm:inline-block">
                  {inputVal.length}/280
                </span>
                <Button
                  type="submit"
                  size="icon-sm"
                  disabled={isSubmitDisabled}
                  className="size-8 rounded-lg shadow-xs transition-transform active:scale-95"
                  aria-label={isPending ? "Sending response..." : "Send response"}
                >
                  {isPending ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Send className="size-4" />
                  )}
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
