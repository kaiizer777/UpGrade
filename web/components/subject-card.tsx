import * as React from "react";
import Link from "next/link";
import { ArrowRight, BookOpen, Calendar, CheckCircle2 } from "lucide-react";
import type { SubjectListItem } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";

export interface SubjectCardProps {
  subject: SubjectListItem;
  topicsDone?: number;
  topicsTotal?: number;
  isSelected?: boolean;
  onSelect?: (id: string) => void;
  className?: string;
}

export function SubjectCard({
  subject,
  topicsDone,
  topicsTotal,
  isSelected = false,
  onSelect,
  className,
}: SubjectCardProps) {
  const isReady = subject.onboarding_status === "ready";
  const hasTopicsCount = topicsTotal !== undefined && topicsTotal > 0;
  const progressPercent = hasTopicsCount
    ? Math.round(((topicsDone ?? 0) / topicsTotal) * 100)
    : 0;

  const formattedDate = new Date(subject.created_at).toLocaleDateString(
    undefined,
    {
      year: "numeric",
      month: "short",
      day: "numeric",
    }
  );

  const href = `/subjects/${subject.id}`;

  return (
    <div
      className={cn(
        "group relative flex flex-col justify-between rounded-xl border border-border/80 bg-card p-5 shadow-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md",
        isSelected && "ring-2 ring-primary border-primary bg-primary/[0.02]",
        className
      )}
    >
      <div className="space-y-3">
        {/* Header: Badge & Date */}
        <div className="flex items-center justify-between gap-2">
          <StatusBadge status={subject.onboarding_status} size="sm" />
          <div className="flex items-center gap-1 text-[11px] text-muted-foreground font-mono">
            <Calendar className="size-3" aria-hidden="true" />
            <time dateTime={subject.created_at}>{formattedDate}</time>
          </div>
        </div>

        {/* Title */}
        <h3 className="font-heading text-lg font-semibold tracking-tight text-foreground transition-colors group-hover:text-primary line-clamp-1">
          <Link
            href={href}
            onClick={() => onSelect?.(subject.id)}
            className="focus-visible:outline-none focus-visible:underline"
          >
            {subject.title}
          </Link>
        </h3>

        {/* Description */}
        <p className="text-xs text-muted-foreground line-clamp-2 min-h-8">
          {subject.description || "No description provided."}
        </p>
      </div>

      {/* Progress & Action Footer */}
      <div className="mt-5 space-y-3 pt-3 border-t border-border/60">
        {/* Topics Count / Progress Bar */}
        {hasTopicsCount ? (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-medium">
              <span className="text-muted-foreground">Topics Progress</span>
              <span className="text-foreground">
                {topicsDone ?? 0}/{topicsTotal} done
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all duration-300 rounded-full"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {isReady ? (
              <>
                <CheckCircle2 className="size-3.5 text-emerald-500 shrink-0" />
                <span>Roadmap ready to explore</span>
              </>
            ) : (
              <>
                <BookOpen className="size-3.5 text-amber-500 shrink-0" />
                <span>Onboarding setup in progress</span>
              </>
            )}
          </div>
        )}

        {/* Action Link */}
        <div className="flex items-center justify-between pt-1 text-xs font-medium">
          <span className="text-muted-foreground text-[11px]">
            {isReady ? "View Roadmap" : "Continue Onboarding"}
          </span>
          <Link
            href={href}
            onClick={() => onSelect?.(subject.id)}
            className="inline-flex items-center gap-1 text-primary transition-transform group-hover:translate-x-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-xs"
            aria-label={`Open ${subject.title}`}
          >
            <span>Open</span>
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </div>
  );
}
