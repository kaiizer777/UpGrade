import * as React from "react";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, CheckCircle2, Compass } from "lucide-react";
import { getFeed, getRoadmap, getSubject } from "@/lib/api";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FeedStream } from "@/components/feed-stream";
import { cn } from "@/lib/utils";

export default async function SubjectFeedPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // 1. Load subject metadata
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

  // If subject is still onboarding, route to onboarding flow
  if (subject.onboarding_status === "onboarding") {
    redirect(`/subjects/${id}/onboarding`);
  }

  // 2. Fetch JIT feed and Roadmap
  let feed;
  let roadmap;
  try {
    [feed, roadmap] = await Promise.all([
      getFeed(id),
      getRoadmap(id).catch(() => null),
    ]);
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
    // If no active topic or roadmap not yet initialized (409/404), redirect to roadmap
    const status = (err as { status?: number })?.status;
    if (status === 409 || status === 404) {
      redirect(`/subjects/${id}/roadmap`);
    }
    throw err;
  }

  // 3. Handle All Topics Completed State
  if (feed.all_topics_completed) {
    return (
      <div className="mx-auto w-full max-w-2xl space-y-6 py-6">
        <div className="flex items-center justify-between">
          <Link
            href={`/subjects/${id}/roadmap`}
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
              "gap-2 text-muted-foreground"
            )}
          >
            <ArrowLeft className="size-4" />
            <span>View Roadmap</span>
          </Link>
        </div>

        <Card className="border-emerald-500/30 bg-emerald-500/5 text-center p-6 sm:p-10 shadow-sm">
          <CardHeader className="space-y-3">
            <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="size-8" />
            </div>
            <CardTitle className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Subject Mastered! 🎉
            </CardTitle>
            <CardDescription className="max-w-md mx-auto text-sm text-muted-foreground">
              You have completed all topics in{" "}
              <span className="font-semibold text-foreground">{subject.title}</span>. Great job
              leveling up your skills!
            </CardDescription>
          </CardHeader>
          <CardFooter className="justify-center pt-4">
            <Link
              href={`/subjects/${id}/roadmap`}
              className={cn(buttonVariants({ size: "lg" }), "gap-2 shadow-xs")}
            >
              <Compass className="size-4" />
              <span>Review Roadmap</span>
            </Link>
          </CardFooter>
        </Card>
      </div>
    );
  }

  // 4. If no topic or no posts returned, redirect to roadmap
  if (!feed.topic || !feed.posts || feed.posts.length === 0) {
    redirect(`/subjects/${id}/roadmap`);
  }

  // 5. Calculate next pending topic for prefetching and last topic status
  const sortedTopics = roadmap?.topics
    ? [...roadmap.topics].sort((a, b) => a.order_index - b.order_index)
    : [];

  const currentTopicIndex = sortedTopics.findIndex((t) => t.id === feed.topic?.id);
  const nextPendingTopic = sortedTopics
    .slice(currentTopicIndex >= 0 ? currentTopicIndex + 1 : 0)
    .find((t) => t.status === "pending");

  const isLastTopic =
    sortedTopics.length > 0 &&
    (currentTopicIndex === sortedTopics.length - 1 ||
      sortedTopics.filter((t) => t.status !== "done").length <= 1);

  return (
    <FeedStream
      subjectId={id}
      subjectTitle={subject.title}
      topic={feed.topic}
      posts={feed.posts}
      nextTopicId={nextPendingTopic ? nextPendingTopic.id : null}
      isLastTopic={isLastTopic}
    />
  );
}
