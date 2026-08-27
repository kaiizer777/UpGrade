import * as React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface RoadmapSkeletonProps {
  className?: string;
}

export function RoadmapSkeleton({ className }: RoadmapSkeletonProps) {
  return (
    <div
      className={cn(
        "mx-auto w-full max-w-4xl space-y-6 animate-in fade-in duration-300",
        className
      )}
      aria-label="Loading roadmap"
      aria-busy="true"
    >
      {/* Top Bar Skeleton */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-36 rounded-md" />
        <Skeleton className="h-6 w-20 rounded-full" />
      </div>

      {/* Header Card Skeleton */}
      <Card className="border-border/80 shadow-xs">
        <CardHeader className="space-y-3">
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-32 rounded-md" />
            <Skeleton className="h-4 w-24 rounded-md" />
          </div>
          <Skeleton className="h-8 w-64 rounded-lg" />
          <Skeleton className="h-4 w-96 rounded-md max-w-full" />
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-border/60 bg-muted/20 p-4">
            <div className="space-y-2">
              <Skeleton className="h-3.5 w-28 rounded-md" />
              <Skeleton className="h-4 w-48 rounded-md" />
            </div>
            <Skeleton className="h-9 w-32 rounded-md" />
          </div>
        </CardContent>
      </Card>

      {/* Topics Timeline Skeleton */}
      <div className="space-y-4 pt-2">
        <Skeleton className="h-6 w-44 rounded-md mb-4" />

        <div className="space-y-0">
          {[1, 2, 3, 4, 5].map((index, _, arr) => {
            const isLast = index === arr.length - 1;
            return (
              <div key={index} className="relative flex gap-4 sm:gap-6">
                {/* Timeline Column: Dot + Connector Line */}
                <div className="flex flex-col items-center">
                  <Skeleton className="size-8 rounded-full shrink-0" />
                  {!isLast && (
                    <div className="w-0.5 grow bg-border/60 my-1.5 min-h-[48px]" />
                  )}
                </div>

                {/* Content Box */}
                <div className={cn("flex-1", !isLast ? "pb-6" : "pb-0")}>
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-border/80 bg-card p-4 sm:p-5 shadow-xs">
                    <div className="space-y-2 flex-1">
                      <div className="flex items-center gap-2">
                        <Skeleton className="h-5 w-8 rounded-md" />
                        <Skeleton className="h-5 w-48 rounded-md" />
                      </div>
                      <Skeleton className="h-3.5 w-32 rounded-md" />
                    </div>
                    <Skeleton className="h-6 w-16 rounded-full shrink-0" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
