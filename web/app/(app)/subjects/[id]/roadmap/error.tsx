"use client";

import * as React from "react";
import { useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertOctagon,
  ArrowLeft,
  RefreshCw,
  ServerCrash,
  Sparkles,
  WifiOff,
} from "lucide-react";
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

export default function RoadmapError({
  error,
  reset,
}: {
  error: Error & { digest?: string; status?: number };
  reset: () => void;
}) {
  const params = useParams();
  const subjectId = params?.id as string | undefined;

  useEffect(() => {
    console.error("[RoadmapError] Route error captured:", error);
  }, [error]);

  const isApiError = error instanceof ApiError || "status" in error;
  const status = isApiError ? (error as { status?: number }).status : undefined;
  const is502 = status === 502 || error.message.includes("502");
  const is503 = status === 503 || error.message.includes("503");
  const is409 = status === 409 || error.message.includes("409");

  return (
    <div className="mx-auto flex min-h-[50vh] w-full max-w-2xl flex-col items-center justify-center p-4 sm:p-6">
      <Card className="w-full border-destructive/30 shadow-md">
        <CardHeader className="space-y-2 text-center">
          <div
            className={cn(
              "mx-auto flex size-12 items-center justify-center rounded-full",
              is502 || is503
                ? "bg-amber-500/10 text-amber-500"
                : is409
                ? "bg-blue-500/10 text-blue-500"
                : "bg-destructive/10 text-destructive"
            )}
          >
            {is503 ? (
              <WifiOff className="size-6" />
            ) : is502 ? (
              <Sparkles className="size-6" />
            ) : is409 ? (
              <ServerCrash className="size-6" />
            ) : (
              <AlertOctagon className="size-6" />
            )}
          </div>

          <CardTitle className="text-xl">
            {is503
              ? "Service Starting Up"
              : is502
              ? "Roadmap Generation Busy"
              : is409
              ? "Onboarding Incomplete"
              : "Failed to Load Roadmap"}
          </CardTitle>

          <CardDescription className="text-xs sm:text-sm">
            {is503
              ? "The backend is temporarily preparing resources. Please retry in a few seconds."
              : is502
              ? "AI model encountered a temporary delay generating your roadmap. Click retry to continue."
              : is409
              ? "Subject onboarding needs to be completed before generating a roadmap."
              : "An unexpected error occurred while loading this curriculum roadmap."}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <div className="rounded-md bg-muted/60 p-3 text-xs font-mono text-muted-foreground break-words">
            {error.message || "Unknown error occurred"}
          </div>
        </CardContent>

        <CardFooter className="flex flex-wrap items-center justify-center gap-3">
          {is409 && subjectId ? (
            <Link
              href={`/subjects/${subjectId}/onboarding`}
              className={cn(buttonVariants({ variant: "default" }), "gap-2")}
            >
              <span>Complete Onboarding</span>
            </Link>
          ) : (
            <Button onClick={() => reset()} className="gap-2 shadow-xs">
              <RefreshCw className="size-4" />
              <span>Retry Roadmap</span>
            </Button>
          )}

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
