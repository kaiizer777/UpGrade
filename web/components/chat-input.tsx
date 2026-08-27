"use client";

import * as React from "react";
import { useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ChatInputProps {
  onSend: (message: string) => Promise<void> | void;
  disabled?: boolean;
  isSending?: boolean;
  placeholder?: string;
  className?: string;
  onEscape?: () => void;
  autoFocus?: boolean;
}

export function ChatInput({
  onSend,
  disabled = false,
  isSending = false,
  placeholder = "Ask a doubt or question about this topic...",
  className,
  onEscape,
  autoFocus = false,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-focus on mount if requested
  useEffect(() => {
    if (autoFocus && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [autoFocus]);

  // Adjust textarea height dynamically to accommodate multiline input
  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 40), 140);
    textarea.style.height = `${newHeight}px`;
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    adjustHeight();
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled || isSending) return;

    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    await onSend(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    } else if (e.key === "Escape") {
      if (onEscape) {
        e.preventDefault();
        onEscape();
      } else {
        textareaRef.current?.blur();
      }
    }
  };

  const isSubmitDisabled = disabled || isSending || !value.trim();

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        "relative flex items-end gap-2 rounded-xl border border-border/80 bg-background/90 p-2 shadow-xs transition-colors focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-ring/30",
        className
      )}
    >
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={handleTextChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled || isSending}
        aria-label="Chat input query"
        className="max-h-[140px] min-h-[40px] flex-1 resize-none bg-transparent px-2.5 py-2 text-xs sm:text-sm text-foreground placeholder:text-muted-foreground focus:outline-hidden disabled:cursor-not-allowed disabled:opacity-50"
      />

      <div className="flex shrink-0 items-center gap-1.5 pb-0.5">
        <Button
          type="submit"
          size="icon-sm"
          disabled={isSubmitDisabled}
          className="size-8 rounded-lg shadow-xs transition-transform active:scale-95"
          aria-label={isSending ? "Sending message..." : "Send doubt"}
        >
          {isSending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Send className="size-4" aria-hidden="true" />
          )}
        </Button>
      </div>
    </form>
  );
}
