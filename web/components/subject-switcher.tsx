"use client";

import * as React from "react";
import { BookMarked, CheckCircle2, Clock } from "lucide-react";
import { useSubject } from "@/hooks/use-subject";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface SubjectSwitcherProps {
  variant?: "pills" | "sidebar";
  className?: string;
}

export function SubjectSwitcher({
  variant = "pills",
  className,
}: SubjectSwitcherProps) {
  const {
    subjects,
    selectedSubjectId,
    selectSubject,
    isLoading,
    error,
  } = useSubject();

  if (isLoading) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 overflow-hidden py-1",
          variant === "sidebar" ? "flex-col items-stretch" : "flex-row",
          className
        )}
      >
        <Skeleton className={cn("h-8 rounded-full", variant === "sidebar" ? "w-full" : "w-28")} />
        <Skeleton className={cn("h-8 rounded-full", variant === "sidebar" ? "w-full" : "w-36")} />
        <Skeleton className={cn("h-8 rounded-full", variant === "sidebar" ? "w-full" : "w-24")} />
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("text-xs text-destructive py-1", className)}>
        Could not load subjects ({error})
      </div>
    );
  }

  if (subjects.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 text-xs text-muted-foreground py-1",
          className
        )}
      >
        <BookMarked className="size-3.5" />
        <span>No subjects available</span>
      </div>
    );
  }

  return (
    <div
      role="tablist"
      aria-label="Subjects"
      aria-orientation={variant === "sidebar" ? "vertical" : "horizontal"}
      className={cn(
        variant === "pills"
          ? "flex w-full items-center gap-1.5 overflow-x-auto py-1 scrollbar-none"
          : "flex w-full flex-col gap-1",
        className
      )}
    >
      {subjects.map((subject) => {
        const isSelected = subject.id === selectedSubjectId;
        const isReady = subject.onboarding_status === "ready";

        return (
          <button
            key={subject.id}
            role="tab"
            type="button"
            aria-selected={isSelected}
            onClick={() => selectSubject(subject.id)}
            className={cn(
              "group relative inline-flex shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
              isSelected
                ? "bg-primary text-primary-foreground shadow-xs"
                : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground",
              variant === "sidebar" && "w-full justify-between rounded-lg px-3 py-2 text-sm"
            )}
          >
            <span className="truncate max-w-[160px] sm:max-w-[200px] text-left">
              {subject.title}
            </span>

            {/* Status dot / indicator */}
            <span className="flex items-center gap-1">
              {isReady ? (
                <CheckCircle2
                  className={cn(
                    "size-3 shrink-0",
                    isSelected ? "text-primary-foreground/90" : "text-emerald-500"
                  )}
                  aria-label="Ready"
                />
              ) : (
                <Clock
                  className={cn(
                    "size-3 shrink-0",
                    isSelected ? "text-primary-foreground/70" : "text-amber-500"
                  )}
                  aria-label="Onboarding"
                />
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
