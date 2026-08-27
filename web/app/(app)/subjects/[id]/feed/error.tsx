"use client";

import * as React from "react";
import { useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertOctagon, ArrowLeft, RefreshCw, Sparkles, WifiOff } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function FeedError({
  error,
  reset,
}: {
  error: Error & { digest?: string; status?: number };
  reset: () => void;
}) {
  const params = useParams();
  const subjectId = params?.id as string | undefined;

  useEffect(() => {
    console.error("[FeedError] Route error captured:", error);
  }, [error]);

  const isApiError = error instanceof ApiError || "status" in error;
  const status = isApiError ? (error as { status?: number }).status : undefined;
  const is502 = status === 502 || error.message.includes("502");
  const is503 = status === 503 || error.message.includes("503");

  return (
    <div className="mx-auto flex min-h-[50vh] w-full max-w-2xl flex-col items-center justify-center p-4 sm:p-6">
      <Card className="w-full border-destructive/30 shadow-md">
        <CardHeader className="space-y-2 text-center">
          <div
            className={cn(
              "mx-auto flex size-12 items-center justify-center rounded-full",
              is502 || is503
                ? "bg-amber-500/10 text-amber-500"
                : "bg-destructive/10 text-destructive"
            )}
          >
            {is503 ? (
              <WifiOff className="size-6" />
            ) : is502 ? (
              <Sparkles className="size-6" />
            ) : (
              <AlertOctagon className="size-6" />
            )}
          </div>

          <CardTitle className="text-xl">
            {is503
              ? "Service Starting Up"
              : is502
              ? "JIT Feed Generation Busy"
              : "Failed to Load Feed"}
          </CardTitle>

          <CardDescription className="text-xs sm:text-sm">
            {is503
              ? "The backend is temporarily preparing resources. Please retry in a few seconds."
              : is502
              ? "AI model feed generator encountered a temporary delay. Click retry to regenerate your lesson batch."
              : "An unexpected error occurred while loading this topic feed."}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <div className="rounded-md bg-muted/60 p-3 text-xs font-mono text-muted-foreground break-words">
            {error.message || "Unknown error occurred"}
          </div>
        </CardContent>

        <CardFooter className="flex flex-wrap items-center justify-center gap-3">
          <Button onClick={() => reset()} className="gap-2 shadow-xs">
            <RefreshCw className="size-4" />
            <span>Retry Feed</span>
          </Button>

          {subjectId && (
            <Link
              href={`/subjects/${subjectId}/roadmap`}
              className={cn(buttonVariants({ variant: "outline" }), "gap-2")}
            >
              <ArrowLeft className="size-4" />
              <span>Back to Roadmap</span>
            </Link>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}
