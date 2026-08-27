"use client";

import * as React from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Briefcase,
  CheckCircle2,
  Compass,
  Flame,
  Gauge,
  GraduationCap,
  Info,
  Loader2,
  Sparkles,
  Target,
} from "lucide-react";
import { toast } from "sonner";
import { createRoadmap } from "@/lib/api";
import type { SubjectProfileSlotRead } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface OnboardingCompleteProps {
  subjectId: string;
  subjectTitle?: string;
  profile?: SubjectProfileSlotRead | null;
  assumptions?: string | null;
  className?: string;
}

export function OnboardingComplete({
  subjectId,
  subjectTitle,
  profile,
  assumptions,
  className,
}: OnboardingCompleteProps) {
  const router = useRouter();
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGoToRoadmap = async () => {
    setIsGenerating(true);
    try {
      // Trigger idempotent roadmap generation
      await createRoadmap(subjectId);
      toast.success("Roadmap initialized successfully!");
      router.push(`/subjects/${subjectId}/roadmap`);
    } catch (err: unknown) {
      console.error("[OnboardingComplete] Failed to create roadmap:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Failed to generate roadmap. Please retry.";
      toast.error(errorMessage, {
        description: "Click to retry generating your learning curriculum.",
        action: {
          label: "Retry",
          onClick: () => void handleGoToRoadmap(),
        },
      });
      setIsGenerating(false);
    }
  };

  return (
    <Card
      className={cn(
        "border-emerald-500/30 bg-card shadow-md overflow-hidden animate-in fade-in-0 duration-300",
        className
      )}
    >
      {/* Header Accent Bar */}
      <div className="h-1.5 w-full bg-gradient-to-r from-emerald-500 via-teal-500 to-primary" />

      <CardHeader className="space-y-3 text-center pb-4">
        <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-8 ring-emerald-500/5">
          <CheckCircle2 className="size-8" />
        </div>
        <div className="space-y-1">
          <CardTitle className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
            Onboarding Completed! 🎉
          </CardTitle>
          <CardDescription className="max-w-md mx-auto text-xs sm:text-sm">
            {subjectTitle ? (
              <>
                Your learning profile for <span className="font-semibold text-foreground">{subjectTitle}</span> has been finalized.
              </>
            ) : (
              "Your personalized learning profile is ready."
            )}
          </CardDescription>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-0">
        {/* Profile Attributes Grid */}
        {profile && (
          <div className="rounded-xl border border-border/70 bg-muted/30 p-4 space-y-3 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-foreground text-xs uppercase tracking-wider text-muted-foreground">
              <Sparkles className="size-3.5 text-amber-500" />
              <span>Tailored Learner Profile</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div className="space-y-1 rounded-lg border border-border/50 bg-background/60 p-2.5">
                <div className="flex items-center gap-1.5 font-medium text-muted-foreground">
                  <Target className="size-3.5 text-primary" />
                  <span>Primary Goal</span>
                </div>
                <p className="text-foreground font-medium line-clamp-2">
                  {profile.goal || "Build fundamental mastery"}
                </p>
              </div>

              <div className="space-y-1 rounded-lg border border-border/50 bg-background/60 p-2.5">
                <div className="flex items-center gap-1.5 font-medium text-muted-foreground">
                  <GraduationCap className="size-3.5 text-primary" />
                  <span>Current Level</span>
                </div>
                <p className="text-foreground font-medium line-clamp-2">
                  {profile.current_level || "Beginner to Intermediate"}
                </p>
              </div>

              <div className="space-y-1 rounded-lg border border-border/50 bg-background/60 p-2.5">
                <div className="flex items-center gap-1.5 font-medium text-muted-foreground">
                  <Briefcase className="size-3.5 text-primary" />
                  <span>Background</span>
                </div>
                <p className="text-foreground font-medium line-clamp-2">
                  {profile.background || "Standard self-paced learner"}
                </p>
              </div>

              <div className="space-y-1 rounded-lg border border-border/50 bg-background/60 p-2.5">
                <div className="flex items-center gap-1.5 font-medium text-muted-foreground">
                  <Flame className="size-3.5 text-amber-500" />
                  <span>Motivation</span>
                </div>
                <p className="text-foreground font-medium line-clamp-2">
                  {profile.motivation || "Skill development and mastery"}
                </p>
              </div>
            </div>

            {/* Pace Preference Badge */}
            <div className="flex items-center justify-between pt-1 border-t border-border/50">
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Gauge className="size-3.5 text-primary" />
                <span>Pace Preference:</span>
              </div>
              <span className="inline-flex items-center rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold capitalize text-primary border border-primary/20">
                {profile.pace_preference || "steady"}
              </span>
            </div>
          </div>
        )}

        {/* Assumptions Notice if applicable */}
        {assumptions && (
          <div className="flex items-start gap-2.5 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-800 dark:text-amber-300">
            <Info className="size-4 shrink-0 text-amber-500 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold">Personalization Assumptions</p>
              <p className="text-[11px] opacity-90 leading-relaxed">{assumptions}</p>
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 border-t border-border/60 bg-muted/20">
        <p className="text-xs text-muted-foreground text-center sm:text-left">
          Ready to construct your ordered curriculum graph.
        </p>

        <Button
          type="button"
          size="default"
          onClick={handleGoToRoadmap}
          disabled={isGenerating}
          className="w-full sm:w-auto gap-2 shadow-xs transition-transform active:scale-95"
        >
          {isGenerating ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              <span>Generating Roadmap...</span>
            </>
          ) : (
            <>
              <Compass className="size-4" />
              <span>Go to Roadmap</span>
              <ArrowRight className="size-4" />
            </>
          )}
        </Button>
      </CardFooter>
    </Card>
  );
}
