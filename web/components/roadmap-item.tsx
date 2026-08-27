import * as React from "react";
import Link from "next/link";
import { ArrowRight, Check, Circle, GitFork, Play } from "lucide-react";
import { StatusBadge } from "@/components/status-badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { RoadmapTopicRead } from "@/lib/types";

export interface RoadmapItemProps {
  topic: RoadmapTopicRead;
  subjectId: string;
  isLast?: boolean;
  topicOrderMap?: Record<number, number>;
}

export function RoadmapItem({
  topic,
  subjectId,
  isLast = false,
  topicOrderMap,
}: RoadmapItemProps) {
  const isActive = topic.status === "active";
  const isDone = topic.status === "done";
  const isPending = topic.status === "pending";

  const prereqLabels =
    topic.prerequisite_ids && topic.prerequisite_ids.length > 0
      ? topic.prerequisite_ids.map((id) =>
          topicOrderMap && topicOrderMap[id] !== undefined
            ? `#${topicOrderMap[id]}`
            : `#${id}`
        )
      : [];

  return (
    <div className="relative flex gap-4 sm:gap-6 group">
      {/* Timeline Column: Dot + Vertical Connector Line */}
      <div className="flex flex-col items-center">
        {/* Circle Dot */}
        <div
          className={cn(
            "relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border transition-all duration-200",
            isDone &&
              "border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-4 ring-emerald-500/10",
            isActive &&
              "border-primary bg-primary text-primary-foreground shadow-sm ring-4 ring-primary/20 scale-105",
            isPending && "border-border bg-card text-muted-foreground/60"
          )}
          aria-hidden="true"
        >
          {isDone ? (
            <Check className="size-4 stroke-[2.5]" />
          ) : isActive ? (
            <Play className="size-3.5 fill-current translate-x-0.5" />
          ) : (
            <Circle className="size-2.5 fill-muted-foreground/30 text-transparent" />
          )}
        </div>

        {/* Vertical Connector Line */}
        {!isLast && (
          <div
            className={cn(
              "w-0.5 grow my-1.5 transition-colors duration-200",
              isDone ? "bg-emerald-500/40" : "bg-border/80"
            )}
            aria-hidden="true"
          />
        )}
      </div>

      {/* Main Content Card */}
      <div className={cn("flex-1 pb-6", isLast && "pb-0")}>
        <div
          className={cn(
            "flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border p-4 sm:p-5 transition-all duration-200",
            isActive
              ? "border-primary/50 bg-primary/[0.03] shadow-xs ring-1 ring-primary/20"
              : isDone
              ? "border-border/60 bg-muted/20 opacity-90"
              : "border-border/80 bg-card hover:border-border"
          )}
        >
          <div className="space-y-1.5 min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded-md bg-muted text-muted-foreground border border-border/60">
                #{topic.order_index + 1}
              </span>
              <h3
                className={cn(
                  "font-semibold text-base tracking-tight text-foreground break-words",
                  isDone && "line-through text-muted-foreground"
                )}
              >
                {topic.title}
              </h3>
            </div>

            {prereqLabels.length > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground pt-0.5">
                <GitFork className="size-3.5 text-muted-foreground/70 shrink-0" />
                <span>
                  Requires:{" "}
                  <span className="font-medium text-foreground/80">
                    {prereqLabels.join(", ")}
                  </span>
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2.5 shrink-0 self-start sm:self-center">
            <StatusBadge status={topic.status} size="sm" />
            {isActive && (
              <Link
                href={`/subjects/${subjectId}/feed`}
                className={cn(
                  buttonVariants({ variant: "default", size: "sm" }),
                  "h-8 gap-1.5 text-xs shadow-xs"
                )}
              >
                <span>Open Feed</span>
                <ArrowRight className="size-3.5" />
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
