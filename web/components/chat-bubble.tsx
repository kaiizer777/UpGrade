"use client";

import * as React from "react";
import { AlertCircle, Bot, RefreshCw, User } from "lucide-react";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ChatBubbleProps {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string | Date;
  isPending?: boolean;
  error?: string | null;
  onRetry?: () => void;
  className?: string;
}

export function ChatBubble({
  role,
  content,
  timestamp,
  isPending = false,
  error = null,
  onRetry,
  className,
}: ChatBubbleProps) {
  const isUser = role === "user";

  const formattedTime = React.useMemo(() => {
    if (!timestamp) return null;
    try {
      const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;
      return date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return null;
    }
  }, [timestamp]);

  return (
    <div
      className={cn(
        "flex items-start gap-2.5 transition-all duration-200",
        isUser ? "ml-auto max-w-[88%] flex-row-reverse" : "mr-auto max-w-[92%]",
        className
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold select-none shadow-2xs",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted border border-border text-primary"
        )}
        aria-hidden="true"
      >
        {isUser ? <User className="size-3.5" /> : <Bot className="size-3.5" />}
      </div>

      {/* Bubble Container */}
      <div className={cn("flex flex-col gap-1", isUser ? "items-end" : "items-start")}>
        {/* Header meta */}
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <span className="font-medium">{isUser ? "You" : "UpGrade Coach"}</span>
          {formattedTime && <span>• {formattedTime}</span>}
          {isPending && <span className="italic text-primary">sending...</span>}
        </div>

        {/* Message Content */}
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-xs sm:text-sm leading-relaxed shadow-2xs",
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-xs"
              : "bg-card text-card-foreground border border-border/80 rounded-tl-xs",
            error && "border-destructive/50 bg-destructive/10 text-destructive"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap leading-relaxed break-words">{content}</p>
          ) : (
            <Markdown content={content} />
          )}
        </div>

        {/* Inline Error and Retry */}
        {error && (
          <div className="flex items-center gap-2 mt-1 text-xs text-destructive">
            <AlertCircle className="size-3.5 shrink-0" />
            <span>{error}</span>
            {onRetry && (
              <Button
                type="button"
                variant="ghost"
                size="xs"
                onClick={onRetry}
                className="h-6 gap-1 px-2 text-[11px] text-destructive hover:bg-destructive/10"
              >
                <RefreshCw className="size-3" />
                <span>Retry</span>
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function ChatBubbleLoading({
  label = "Thinking...",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 mr-auto max-w-[90%] animate-in fade-in-0 duration-200",
        className
      )}
      role="status"
      aria-label={label}
    >
      <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted border border-border text-primary shadow-2xs">
        <Bot className="size-3.5" />
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="text-[10px] font-medium text-muted-foreground">UpGrade Coach</span>
        <div className="flex items-center gap-2 rounded-2xl rounded-tl-xs border border-border/80 bg-card px-4 py-3 text-xs text-muted-foreground shadow-2xs">
          <span className="flex gap-1" aria-hidden="true">
            <span className="size-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.3s]" />
            <span className="size-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.15s]" />
            <span className="size-1.5 rounded-full bg-primary animate-bounce" />
          </span>
          <span className="ml-1 text-xs">{label}</span>
        </div>
      </div>
    </div>
  );
}
