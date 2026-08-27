"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertOctagon, ArrowLeft, RefreshCw, ServerCrash, WifiOff } from "lucide-react";
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

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string; status?: number };
  reset: () => void;
}) {
  useEffect(() => {
    // Log error to monitoring if configured
    console.error("Application error:", error);
  }, [error]);

  const isApiError = error instanceof ApiError || "status" in error;
  const status = isApiError
    ? (error as { status?: number }).status
    : undefined;

  const is502 = status === 502 || error.message.includes("502");
  const is503 = status === 503 || error.message.includes("503");
  const isServiceError = is502 || is503;

  return (
    <div className="flex min-h-[70vh] items-center justify-center p-4 sm:p-8">
      <Card className="w-full max-w-lg border-destructive/30 shadow-lg">
        <CardHeader className="space-y-2 text-center">
          <div
            className={cn(
              "mx-auto flex size-12 items-center justify-center rounded-full",
              isServiceError
                ? "bg-amber-500/10 text-amber-500"
                : "bg-destructive/10 text-destructive"
            )}
          >
            {is503 ? (
              <WifiOff className="size-6" />
            ) : is502 ? (
              <ServerCrash className="size-6" />
            ) : (
              <AlertOctagon className="size-6" />
            )}
          </div>

          <CardTitle className="text-xl">
            {is503
              ? "Service Temporarily Unavailable"
              : is502
              ? "Upstream Service Error"
              : "Something Went Wrong"}
          </CardTitle>

          <CardDescription className="text-sm">
            {is503
              ? "The AI service or backend is currently starting up or unavailable. Please retry."
              : is502
              ? "Failed to communicate with upstream AI provider. Please retry."
              : "An unexpected error occurred while loading this page."}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <div className="rounded-md bg-muted/60 p-3 text-xs font-mono text-muted-foreground break-words">
            {error.message || "Unknown client or server error"}
            {error.digest && (
              <div className="mt-1 text-[10px] text-muted-foreground/70">
                Digest: {error.digest}
              </div>
            )}
          </div>
        </CardContent>

        <CardFooter className="flex flex-wrap items-center justify-center gap-3">
          <Button onClick={() => reset()} className="gap-2">
            <RefreshCw className="size-4" />
            <span>Try Again</span>
          </Button>
          <Link
            href="/subjects"
            className={cn(buttonVariants({ variant: "outline" }), "gap-2")}
          >
            <ArrowLeft className="size-4" />
            <span>Back to Subjects</span>
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}
