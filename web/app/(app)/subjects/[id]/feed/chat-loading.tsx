import { Skeleton } from "@/components/ui/skeleton";

export default function ChatLoading() {
  return (
    <div
      className="flex h-full w-full flex-col overflow-hidden bg-background p-4"
      aria-label="Loading chat"
    >
      {/* Header skeleton */}
      <div className="flex flex-col gap-2 border-b border-border/80 pb-4">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-3 w-64" />
      </div>

      {/* Message stream skeletons */}
      <div className="flex-1 space-y-4 py-4">
        {/* Assistant turn */}
        <div className="flex items-start gap-3 mr-auto max-w-[85%]">
          <Skeleton className="size-7 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-16 w-full rounded-2xl rounded-tl-xs" />
          </div>
        </div>

        {/* User turn */}
        <div className="flex items-start gap-3 ml-auto max-w-[80%] flex-row-reverse">
          <Skeleton className="size-7 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-16 ml-auto" />
            <Skeleton className="h-12 w-full rounded-2xl rounded-tr-xs" />
          </div>
        </div>

        {/* Assistant response */}
        <div className="flex items-start gap-3 mr-auto max-w-[85%]">
          <Skeleton className="size-7 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-24 w-full rounded-2xl rounded-tl-xs" />
          </div>
        </div>
      </div>

      {/* Input bar skeleton */}
      <div className="border-t border-border/80 pt-3">
        <Skeleton className="h-12 w-full rounded-xl" />
      </div>
    </div>
  );
}
