import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Compass,
  Sparkles,
} from "lucide-react";
import { getRoadmap, getSubject } from "@/lib/api";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { RoadmapItem } from "@/components/roadmap-item";
import { GenerateRoadmapButton } from "@/components/generate-roadmap-button";
import { cn } from "@/lib/utils";

export default async function SubjectRoadmapPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let subject;
  try {
    subject = await getSubject(id);
  } catch (err) {
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

  if (subject.onboarding_status === "onboarding") {
    redirect(`/subjects/${id}/onboarding`);
  }

  let roadmap = null;
  try {
    roadmap = await getRoadmap(id);
  } catch (err) {
    console.warn("[RoadmapPage] Failed to fetch roadmap:", err);
  }

  const topics = roadmap?.topics
    ? [...roadmap.topics].sort((a, b) => a.order_index - b.order_index)
    : [];

  const completedTopicsCount = topics.filter((t) => t.status === "done").length;
  const activeTopic =
    topics.find((t) => t.status === "active") ||
    (completedTopicsCount === 0 ? topics.find((t) => t.status === "pending") : undefined);
  const allCompleted = topics.length > 0 && completedTopicsCount === topics.length;

  // Map topic id -> 1-based order index for prerequisite labels
  const topicOrderMap: Record<number, number> = Object.fromEntries(
    topics.map((t) => [t.id, t.order_index + 1])
  );

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6">
      {/* Top bar */}
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
        <StatusBadge status={subject.onboarding_status} />
      </div>

      {/* Subject Header Card */}
      <Card className="border-border/80 shadow-xs">
        <CardHeader className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-emerald-500">
              <Compass className="size-5" />
              <span className="text-xs font-semibold tracking-wide uppercase">
                Learning Roadmap
              </span>
            </div>
            {topics.length > 0 && (
              <span className="text-xs font-medium text-muted-foreground">
                {completedTopicsCount}/{topics.length} topics done
              </span>
            )}
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">
            {subject.title}
          </CardTitle>
          <CardDescription>
            {subject.description || "Personalized learning curriculum."}
          </CardDescription>
        </CardHeader>

        {/* Active Topic Banner */}
        {activeTopic && (
          <CardContent className="pt-0">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-primary/20 bg-primary/5 p-4">
              <div className="space-y-0.5 min-w-0">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-primary uppercase tracking-wider">
                  <Sparkles className="size-3.5" />
                  <span>Current Active Topic</span>
                </div>
                <p className="text-sm font-medium text-foreground truncate">
                  #{activeTopic.order_index + 1}. {activeTopic.title}
                </p>
              </div>

              <Link
                href={`/subjects/${id}/feed`}
                className={cn(
                  buttonVariants({ size: "default" }),
                  "gap-2 shadow-xs shrink-0"
                )}
              >
                <span>
                  {completedTopicsCount === 0 ? "Start Learning" : "Continue Feed"}
                </span>
                <ArrowRight className="size-4" />
              </Link>
            </div>
          </CardContent>
        )}

        {/* All Completed Banner */}
        {allCompleted && (
          <CardContent className="pt-0">
            <div className="flex items-center justify-between gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="size-5 text-emerald-500 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    All topics completed!
                  </p>
                  <p className="text-xs text-muted-foreground">
                    You have mastered the curriculum for this subject.
                  </p>
                </div>
              </div>
              <Link
                href={`/subjects/${id}/feed`}
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                  "gap-1.5 shrink-0 text-xs"
                )}
              >
                <span>Review Feed</span>
                <ArrowRight className="size-3.5" />
              </Link>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Topics Timeline */}
      {topics.length > 0 ? (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold tracking-tight text-foreground">
            Curriculum Sequence
          </h2>

          <div className="space-y-0">
            {topics.map((t, index) => (
              <RoadmapItem
                key={t.id}
                topic={t}
                subjectId={id}
                isLast={index === topics.length - 1}
                topicOrderMap={topicOrderMap}
              />
            ))}
          </div>
        </div>
      ) : (
        <Card className="border-dashed border-2 p-8 sm:p-12 text-center bg-card/40">
          <CardHeader className="space-y-3 max-w-md mx-auto">
            <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <BookOpen className="size-6" />
            </div>
            <CardTitle className="text-xl font-bold">
              No Roadmap Generated Yet
            </CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              Generate your personalized curriculum sequence to start learning step by step.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-2 flex justify-center">
            <GenerateRoadmapButton subjectId={id} size="lg" />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
