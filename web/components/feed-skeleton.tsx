import * as React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";

export function FeedSkeleton() {
  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 animate-in fade-in duration-300">
      {/* Header Skeleton */}
      <div className="flex flex-col gap-4 border-b border-border/60 pb-5">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-28 rounded-md" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-7 w-3/4 rounded-lg" />
          <Skeleton className="h-4 w-1/2 rounded-md" />
        </div>
      </div>

      {/* Posts Stream Skeletons */}
      <div className="space-y-4" aria-label="Loading feed posts" aria-busy="true">
        {[1, 2, 3, 4].map((index) => (
          <Card key={index} className="border-border/80 shadow-xs overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <div className="flex items-center gap-2">
                <Skeleton className="size-6 rounded-full" />
                <Skeleton className="h-4 w-20 rounded-md" />
              </div>
              <Skeleton className="h-3 w-16 rounded-md" />
            </CardHeader>

            <CardContent className="space-y-2.5 pt-1 pb-3">
              <Skeleton className="h-4 w-full rounded-md" />
              <Skeleton className="h-4 w-[92%] rounded-md" />
              <Skeleton className="h-4 w-[78%] rounded-md" />
            </CardContent>

            <CardFooter className="flex items-center justify-between border-t border-border/40 pt-2.5 pb-2.5 bg-muted/20">
              <Skeleton className="h-7 w-24 rounded-md" />
              <Skeleton className="h-3 w-14 rounded-md" />
            </CardFooter>
          </Card>
        ))}
      </div>

      {/* Footer Complete Button Skeleton */}
      <div className="pt-4 flex justify-center">
        <Skeleton className="h-11 w-full sm:w-64 rounded-xl" />
      </div>
    </div>
  );
}
