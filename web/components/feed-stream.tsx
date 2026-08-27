"use client";

import * as React from "react";
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Layers, MessageSquare, Sparkles } from "lucide-react";
import type { FeedPostRead, FeedTopicSummary } from "@/lib/types";
import { usePrefetch } from "@/hooks/use-prefetch";
import { FeedCard } from "@/components/feed-card";
import { CompleteTopicButton } from "@/components/complete-topic-button";
import { ChatSheet } from "@/components/chat-sheet";
import { StatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface FeedStreamProps {
  subjectId: string;
  subjectTitle: string;
  topic: FeedTopicSummary;
  posts: FeedPostRead[];
  nextTopicId?: number | null;
  isLastTopic?: boolean;
}

export function FeedStream({
  subjectId,
  subjectTitle,
  topic,
  posts,
  nextTopicId,
  isLastTopic = false,
}: FeedStreamProps) {
  const [selectedPostForChat, setSelectedPostForChat] = useState<FeedPostRead | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);

  // Hook for 70% prefetch of the next pending topic
  const { targetRef, hasPrefetched } = usePrefetch({
    subjectId,
    nextTopicId,
    threshold: 0.7,
    enabled: Boolean(nextTopicId),
  });

  const handleOpenChat = (post?: FeedPostRead) => {
    setSelectedPostForChat(post || null);
    setIsChatOpen(true);
  };

  // Determine index where ~70% threshold is reached (0-indexed)
  const prefetchIndex = Math.max(0, Math.floor(posts.length * 0.7) - 1);

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6">
      {/* Feed Header */}
      <div className="flex flex-col gap-3 border-b border-border/60 pb-5">
        <div className="flex items-center justify-between">
          <Link
            href={`/subjects/${subjectId}/roadmap`}
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
              "gap-2 text-muted-foreground hover:text-foreground -ml-2"
            )}
          >
            <ArrowLeft className="size-4" />
            <span>Roadmap</span>
          </Link>

          <div className="flex items-center gap-2">
            {hasPrefetched && nextTopicId && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                <Sparkles className="size-3" />
                Next Topic Ready
              </span>
            )}
            <StatusBadge status={topic.status} size="sm" />
          </div>
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary">
            <Layers className="size-4" />
            <span>Topic {topic.order_index + 1}</span>
            <span className="text-muted-foreground">•</span>
            <span className="text-muted-foreground font-normal lowercase">
              {posts.length} {posts.length === 1 ? "post" : "posts"}
            </span>
          </div>

          <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            {topic.title}
          </h1>
          <p className="text-xs text-muted-foreground font-mono">
            {subjectTitle}
          </p>
        </div>
      </div>

      {/* Feed Posts Stream */}
      <div className="space-y-4" role="feed" aria-label={`Lessons for ${topic.title}`}>
        {posts.map((post, index) => {
          const isPrefetchTrigger = index === prefetchIndex && Boolean(nextTopicId);

          return (
            <div
              key={post.id}
              ref={isPrefetchTrigger ? targetRef : undefined}
              className="relative"
            >
              <FeedCard
                post={post}
                totalPosts={posts.length}
                topicTitle={topic.title}
                onOpenChat={handleOpenChat}
              />
            </div>
          );
        })}
      </div>

      {/* Complete Topic Action Footer */}
      <div className="mt-8 flex flex-col items-center justify-center gap-4 rounded-xl border border-border/80 bg-muted/20 p-6 text-center shadow-xs">
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-foreground">
            {isLastTopic ? "Ready to wrap up this subject?" : "Finished this lesson batch?"}
          </h3>
          <p className="text-xs text-muted-foreground max-w-md">
            {isLastTopic
              ? "Mark this final topic complete to finish your learning journey for this subject."
              : "Mark complete to clean up ephemeral feed posts and advance directly to the next topic."}
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3 w-full sm:w-auto">
          <CompleteTopicButton
            topicId={topic.id}
            subjectId={subjectId}
            topicTitle={topic.title}
            isLastTopic={isLastTopic}
          />

          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => handleOpenChat()}
            className="gap-2 sm:w-auto w-full"
          >
            <MessageSquare className="size-4 text-primary" />
            <span>Ask Doubts</span>
          </Button>
        </div>
      </div>

      {/* Doubts Chat Sheet */}
      <ChatSheet
        open={isChatOpen}
        onOpenChange={setIsChatOpen}
        subjectId={subjectId}
        topicId={topic.id}
        topicTitle={topic.title}
        initialPost={selectedPostForChat}
      />
    </div>
  );
}
