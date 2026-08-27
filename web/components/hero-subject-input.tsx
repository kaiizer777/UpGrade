"use client";

import * as React from "react";
import { useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const POPULAR_SUBJECTS = [
  "Machine Learning",
  "System Design",
  "Distributed Systems",
  "Rust Programming",
];

export interface HeroSubjectInputProps {
  className?: string;
  placeholder?: string;
  onSubmit?: (subject: string) => void;
}

export function HeroSubjectInput({
  className,
  placeholder = "Enter your first subject... (e.g. Machine Learning, Rust)",
  onSubmit,
}: HeroSubjectInputProps) {
  const [value, setValue] = useState("");
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    onSubmit?.(trimmed);
  };

  const handleSelectSuggestion = (suggestion: string) => {
    setValue(suggestion);
    inputRef.current?.focus();
  };

  return (
    <div className={cn("mx-auto mt-8 w-full max-w-xl", className)}>
      <form
        onSubmit={handleSubmit}
        className="group relative flex items-center rounded-2xl border border-primary/60 bg-card/60 p-1.5 shadow-2xl backdrop-blur-xl ring-4 ring-primary/10 transition-all duration-300 focus-within:border-primary focus-within:ring-primary/20"
      >
        <div className="flex size-10 items-center justify-center rounded-xl text-primary transition-colors pl-2">
          <Sparkles className="size-4 shrink-0" aria-hidden="true" />
        </div>

        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          className="h-11 flex-1 bg-transparent px-3 text-base text-foreground placeholder:text-muted-foreground/60 outline-none sm:text-sm"
          aria-label="Enter your first subject"
        />

        <div className="flex items-center gap-1.5 pr-1">
          <span className="hidden sm:inline-flex items-center rounded-md border border-border/60 bg-muted/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground select-none">
            ↵ Enter
          </span>

          <button
            type="submit"
            disabled={!value.trim()}
            className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md transition-all hover:bg-primary/90 hover:scale-105 active:scale-95 disabled:opacity-40 disabled:hover:scale-100 disabled:cursor-not-allowed"
            aria-label="Start subject"
          >
            <ArrowRight className="size-4" />
          </button>
        </div>
      </form>

      {/* Suggestion Chips */}
      <div className="mt-3 flex flex-wrap items-center justify-center gap-1.5 text-xs text-muted-foreground">
        <span className="text-muted-foreground/60 text-[11px]">Popular:</span>
        {POPULAR_SUBJECTS.map((topic) => (
          <button
            key={topic}
            type="button"
            onClick={() => handleSelectSuggestion(topic)}
            className="rounded-full border border-border/60 bg-muted/30 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground transition-all hover:border-primary/40 hover:bg-muted/70 hover:text-foreground active:scale-95"
          >
            {topic}
          </button>
        ))}
      </div>
    </div>
  );
}
