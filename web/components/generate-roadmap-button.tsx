"use client";

import * as React from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { ApiError, createRoadmap, getRoadmap } from "@/lib/api";
import type { RoadmapRead } from "@/lib/types";
import { Button, type buttonVariants } from "@/components/ui/button";
import type { VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// In-memory set for deduplicating client-side generation calls
const generatedSubjects = new Set<string>();

export interface GenerateRoadmapButtonProps {
  subjectId: string;
  variant?: VariantProps<typeof buttonVariants>["variant"];
  size?: VariantProps<typeof buttonVariants>["size"];
  className?: string;
  disabled?: boolean;
  children?: React.ReactNode;
  onSuccess?: (roadmap: RoadmapRead) => void;
}

export function GenerateRoadmapButton({
  subjectId,
  variant = "default",
  size = "default",
  className,
  disabled = false,
  children,
  onSuccess,
}: GenerateRoadmapButtonProps) {
  const router = useRouter();
  const [isPending, setIsPending] = useState(false);

  const handleGenerate = async () => {
    if (isPending || disabled) return;

    setIsPending(true);
    try {
      // Client guard: if already generated or GET roadmap already has topics, skip POST
      if (generatedSubjects.has(subjectId)) {
        const existing = await getRoadmap(subjectId).catch(() => null);
        if (existing && existing.topics && existing.topics.length > 0) {
          router.refresh();
          onSuccess?.(existing);
          setIsPending(false);
          return;
        }
      }

      // Trigger idempotent creation endpoint
      const roadmap = await createRoadmap(subjectId);
      generatedSubjects.add(subjectId);

      // If backend returned topics immediately
      if (roadmap.topics && roadmap.topics.length > 0) {
        toast.success("Learning roadmap created successfully!");
        router.refresh();
        onSuccess?.(roadmap);
        return;
      }

      // Post-create polling: if topics not yet populated, poll GET roadmap
      let attempts = 0;
      const maxAttempts = 5;
      let finalRoadmap: RoadmapRead = roadmap;

      while (attempts < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, 1000 * (attempts + 1)));
        try {
          const polled = await getRoadmap(subjectId);
          if (polled.topics && polled.topics.length > 0) {
            finalRoadmap = polled;
            break;
          }
        } catch {
          // Continue next polling attempt
        }
        attempts++;
      }

      toast.success("Learning roadmap ready!");
      router.refresh();
      onSuccess?.(finalRoadmap);
    } catch (err: unknown) {
      console.error("[GenerateRoadmapButton] Failed to create roadmap:", err);

      const status =
        err instanceof ApiError
          ? err.status
          : typeof err === "object" && err !== null && "status" in err
          ? (err as { status?: number }).status
          : undefined;

      let errorMessage = "Failed to generate learning roadmap.";
      let description = "Please retry generating your curriculum.";

      if (status === 503) {
        errorMessage = "Service temporarily unavailable (503)";
        description = "The AI service is initializing. Please retry in a few seconds.";
      } else if (status === 502) {
        errorMessage = "AI generation temporarily busy (502)";
        description = "Upstream AI model encountered a delay. Click retry to regenerate.";
      } else if (status === 409) {
        errorMessage = "Onboarding incomplete (409)";
        description = "Please finalize onboarding questions before generating your roadmap.";
      } else if (err instanceof Error && err.message) {
        errorMessage = err.message;
      }

      toast.error(errorMessage, {
        description,
        action: {
          label: "Retry",
          onClick: () => {
            void handleGenerate();
          },
        },
      });
    } finally {
      setIsPending(false);
    }
  };

  return (
    <Button
      onClick={() => void handleGenerate()}
      disabled={isPending || disabled}
      variant={variant}
      size={size}
      className={cn("gap-2 shadow-xs", className)}
      aria-busy={isPending}
    >
      {isPending ? (
        <>
          <Loader2 className="size-4 animate-spin" />
          <span>Generating Roadmap...</span>
        </>
      ) : (
        <>
          <Sparkles className="size-4" />
          <span>{children ?? "Generate Roadmap"}</span>
        </>
      )}
    </Button>
  );
}
