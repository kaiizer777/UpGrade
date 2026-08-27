import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, MessageSquareText } from "lucide-react";
import { getOnboardingState, getSubject } from "@/lib/api";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { OnboardingView } from "@/components/onboarding-view";
import { StatusBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";

export default async function SubjectOnboardingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // 1. Fetch Subject metadata in RSC
  let subject;
  try {
    subject = await getSubject(id);
  } catch (err: unknown) {
    if (
      err &&
      typeof err === "object" &&
      "digest" in err &&
      typeof (err as { digest?: string }).digest === "string" &&
      ((err as { digest: string }).digest.startsWith("NEXT_REDIRECT") ||
        (err as { digest: string }).digest.startsWith("NEXT_NOT_FOUND"))
    ) {
      throw err;
    }
    notFound();
  }

  if (!subject) {
    notFound();
  }

  // 2. Fetch initial onboarding state in RSC
  let initialState = null;
  try {
    initialState = await getOnboardingState(id);
  } catch (err: unknown) {
    console.warn("[SubjectOnboardingPage] Could not pre-fetch onboarding state:", err);
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6">
      {/* Top Action Bar */}
      <div className="flex items-center justify-between">
        <Link
          href="/subjects"
          className={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            "gap-2 text-muted-foreground"
          )}
        >
          <ArrowLeft className="size-4" />
          <span>Back to Subjects</span>
        </Link>
        <StatusBadge status={initialState?.status || subject.onboarding_status} />
      </div>

      {/* Subject Header Card */}
      <Card className="border-border/80 shadow-xs">
        <CardHeader className="space-y-2">
          <div className="flex items-center gap-2 text-amber-500">
            <MessageSquareText className="size-5" />
            <span className="text-xs font-semibold tracking-wide uppercase">
              Onboarding Track
            </span>
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">
            {subject.title}
          </CardTitle>
          <CardDescription>
            {subject.description || "Personalized onboarding interview."}
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Interactive Client Island */}
      <OnboardingView
        subjectId={subject.id}
        subjectTitle={subject.title}
        subjectDescription={subject.description}
        initialState={initialState}
      />
    </div>
  );
}
