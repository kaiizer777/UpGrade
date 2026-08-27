import { Skeleton } from "@/components/ui/skeleton";

export default function OnboardingLoading() {
  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 animate-in fade-in-0 duration-200">
      {/* Top action bar */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-32 rounded-lg" />
        <Skeleton className="h-6 w-24 rounded-full" />
      </div>

      {/* Subject Header Card Skeleton */}
      <div className="rounded-xl border border-border/80 bg-card p-6 shadow-xs space-y-3">
        <div className="flex items-center gap-2">
          <Skeleton className="size-4 rounded-full" />
          <Skeleton className="h-4 w-28" />
        </div>
        <Skeleton className="h-7 w-64 sm:w-80" />
        <Skeleton className="h-4 w-full max-w-md" />
      </div>

      {/* Progress Widget Skeleton */}
      <div className="rounded-xl border border-border/80 bg-card p-4 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-2">
            <Skeleton className="h-3.5 w-32" />
            <div className="flex items-center gap-1.5">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-1.5 w-4 rounded-full" />
              ))}
            </div>
          </div>
          <div className="space-y-1 sm:text-right">
            <Skeleton className="h-3 w-28 sm:ml-auto" />
            <Skeleton className="h-4 w-12 sm:ml-auto" />
          </div>
        </div>

        <div className="pt-2 border-t border-border/60 space-y-2">
          <Skeleton className="h-3 w-36" />
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-24 rounded-md" />
            ))}
          </div>
        </div>
      </div>

      {/* Chat Thread Skeleton */}
      <div className="rounded-xl border border-border/80 bg-background shadow-xs overflow-hidden">
        <div className="p-4 space-y-4 min-h-[380px]">
          {/* Assistant Bubble */}
          <div className="flex items-start gap-2.5 mr-auto max-w-[85%]">
            <Skeleton className="size-7 rounded-full shrink-0" />
            <div className="space-y-2 flex-1">
              <Skeleton className="h-3.5 w-24" />
              <Skeleton className="h-16 w-full rounded-2xl rounded-tl-xs" />
            </div>
          </div>

          {/* User Bubble */}
          <div className="flex items-start gap-2.5 ml-auto max-w-[75%] flex-row-reverse">
            <Skeleton className="size-7 rounded-full shrink-0" />
            <div className="space-y-2 flex-1 items-end">
              <Skeleton className="h-3.5 w-16 ml-auto" />
              <Skeleton className="h-12 w-full rounded-2xl rounded-tr-xs" />
            </div>
          </div>

          {/* Assistant Bubble */}
          <div className="flex items-start gap-2.5 mr-auto max-w-[85%]">
            <Skeleton className="size-7 rounded-full shrink-0" />
            <div className="space-y-2 flex-1">
              <Skeleton className="h-3.5 w-24" />
              <Skeleton className="h-20 w-full rounded-2xl rounded-tl-xs" />
            </div>
          </div>
        </div>

        {/* Input Bar Skeleton */}
        <div className="border-t border-border/80 bg-muted/20 p-3">
          <Skeleton className="h-12 w-full rounded-xl" />
        </div>
      </div>
    </div>
  );
}
