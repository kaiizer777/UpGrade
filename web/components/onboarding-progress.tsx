"use client";

import * as React from "react";
import {
  CheckCircle2,
  Circle,
  Info,
  Target,
  GraduationCap,
  Briefcase,
  Flame,
  Gauge,
} from "lucide-react";
import type { CompletenessRead, SubjectProfileSlotRead } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface OnboardingProgressProps {
  questionsAsked: number;
  maxQuestions?: number;
  completeness: CompletenessRead;
  profile?: SubjectProfileSlotRead | null;
  status?: string;
  className?: string;
}

interface SlotMeta {
  key: string;
  label: string;
  icon: React.ElementType;
}

const PROFILE_SLOTS: SlotMeta[] = [
  { key: "goal", label: "Goal", icon: Target },
  { key: "current_level", label: "Current Level", icon: GraduationCap },
  { key: "background", label: "Background", icon: Briefcase },
  { key: "motivation", label: "Motivation", icon: Flame },
  { key: "pace_preference", label: "Pace", icon: Gauge },
];

export function OnboardingProgress({
  questionsAsked,
  maxQuestions = 10,
  completeness,
  profile,
  status,
  className,
}: OnboardingProgressProps) {
  const score = Math.max(0, Math.min(100, completeness?.score ?? 0));
  const isCapReached = questionsAsked >= maxQuestions;
  const isReady = status === "ready" || profile?.status === "ready";

  const filledSlotKeys = React.useMemo(() => {
    const set = new Set(completeness?.filled_slots ?? []);
    // Normalize pace / pace_preference if either is present
    if (set.has("pace")) set.add("pace_preference");
    if (set.has("pace_preference")) set.add("pace");
    return set;
  }, [completeness?.filled_slots]);

  const getSlotValue = (key: string): string | null => {
    if (!profile) return null;
    if (key === "goal") return profile.goal || null;
    if (key === "current_level") return profile.current_level || null;
    if (key === "background") return profile.background || null;
    if (key === "motivation") return profile.motivation || null;
    if (key === "pace_preference" || key === "pace") return profile.pace_preference || null;
    return null;
  };

  return (
    <div className={cn("rounded-xl border border-border/80 bg-card p-4 shadow-xs space-y-3.5", className)}>
      {/* Top row: Questions budget dots and completeness score */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Questions Budget
            </span>
            <span className="font-mono text-xs font-medium text-foreground">
              {Math.min(questionsAsked, maxQuestions)}/{maxQuestions}
            </span>
          </div>

          {/* Dots Indicator 1..10 */}
          <div className="flex items-center gap-1" aria-label={`Questions asked: ${questionsAsked} of ${maxQuestions}`}>
            {Array.from({ length: maxQuestions }).map((_, idx) => {
              const isAnswered = idx < questionsAsked;
              const isCurrent = idx === questionsAsked && !isReady;

              return (
                <div
                  key={idx}
                  title={`Question ${idx + 1} of ${maxQuestions}`}
                  className={cn(
                    "h-1.5 rounded-full transition-all duration-300",
                    isAnswered
                      ? "w-4 sm:w-5 bg-primary"
                      : isCurrent
                      ? "w-3 sm:w-4 bg-primary/40 animate-pulse"
                      : "w-2 sm:w-2.5 bg-muted-foreground/20"
                  )}
                />
              );
            })}
          </div>
        </div>

        {/* Completeness Score */}
        <div className="flex items-center sm:justify-end gap-2.5">
          <div className="text-left sm:text-right">
            <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              Profile Completeness
            </div>
            <div className="font-mono text-sm font-bold text-foreground">
              {score}%
            </div>
          </div>

          {/* Mini circular or linear score indicator */}
          <div className="h-2 w-20 sm:w-24 rounded-full bg-muted overflow-hidden">
            <div
              className={cn(
                "h-full transition-all duration-500 rounded-full",
                score >= 100
                  ? "bg-emerald-500"
                  : score >= 60
                  ? "bg-primary"
                  : "bg-amber-500"
              )}
              style={{ width: `${score}%` }}
            />
          </div>
        </div>
      </div>

      {/* Completeness Chips for the 5 profile dimensions */}
      <div className="space-y-1.5 pt-1 border-t border-border/60">
        <div className="text-[11px] font-medium text-muted-foreground">
          Profile Dimensions ({filledSlotKeys.size > 5 ? 5 : filledSlotKeys.size}/5):
        </div>
        <div className="flex flex-wrap gap-1.5">
          {PROFILE_SLOTS.map(({ key, label, icon: Icon }) => {
            const isFilled = filledSlotKeys.has(key);
            const value = getSlotValue(key);

            return (
              <div
                key={key}
                title={value ? `${label}: ${value}` : `${label}: Missing`}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors select-none",
                  isFilled
                    ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30"
                    : "bg-muted/50 text-muted-foreground border border-border/60"
                )}
              >
                {isFilled ? (
                  <CheckCircle2 className="size-3 text-emerald-500 shrink-0" />
                ) : (
                  <Circle className="size-3 text-muted-foreground/60 shrink-0" />
                )}
                <Icon className="size-3 opacity-80 shrink-0" />
                <span className="truncate max-w-[120px]">{label}</span>
                {isFilled && value && (
                  <span className="hidden md:inline-block max-w-[80px] truncate text-[10px] opacity-70 font-normal">
                    • {value}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 10-Question Hard Cap Notification */}
      {isCapReached && !isReady && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-800 dark:text-amber-300">
          <Info className="size-4 shrink-0 text-amber-500 mt-0.5" />
          <div className="space-y-0.5">
            <p className="font-semibold">Question limit (10/10) reached</p>
            <p className="text-[11px] opacity-90 leading-relaxed">
              UpGrade will synthesize your responses and apply default assumptions for any remaining missing slots to finalize your roadmap.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
