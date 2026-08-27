"use client";

import * as React from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, PartyPopper } from "lucide-react";
import { toast } from "sonner";
import { completeTopic } from "@/lib/api";
import type { TopicCompleteResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface CompleteTopicButtonProps {
  topicId: number;
  subjectId: string;
  topicTitle?: string;
  isLastTopic?: boolean;
  onCompleted?: (response: TopicCompleteResponse) => void;
  className?: string;
}

/**
 * Button component to mark a topic as complete.
 * Strict rule: Waits for POST /topics/{id}/complete transaction to resolve
 * on the backend before swapping views or advancing to the next topic.
 */
export function CompleteTopicButton({
  topicId,
  subjectId,
  topicTitle,
  isLastTopic = false,
  onCompleted,
  className,
}: CompleteTopicButtonProps) {
  const router = useRouter();
  const [isPending, setIsPending] = useState(false);

  const handleComplete = async () => {
    if (isPending) return;

    setIsPending(true);

    try {
      const result = await completeTopic(topicId);

      if (result.all_topics_completed) {
        toast.success("🎉 All topics completed! Subject mastered!", {
          description: "Returning to roadmap overview.",
        });
      } else if (result.next_topic_title) {
        toast.success(`Completed "${topicTitle || "Topic"}"!`, {
          description: `Up next: ${result.next_topic_title}`,
        });
      } else {
        toast.success(`Topic completed successfully!`);
      }

      if (onCompleted) {
        onCompleted(result);
      }

      if (result.all_topics_completed) {
        router.push(`/subjects/${subjectId}/roadmap`);
      } else {
        // Refresh server component to fetch new active topic's feed
        router.refresh();
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to mark topic as complete";

      toast.error("Topic completion failed", {
        description: message,
        action: {
          label: "Retry",
          onClick: () => handleComplete(),
        },
      });
      setIsPending(false);
    }
  };

  return (
    <Button
      type="button"
      size="lg"
      onClick={handleComplete}
      disabled={isPending}
      className={cn(
        "relative gap-2 font-medium shadow-md transition-all sm:w-auto w-full",
        isLastTopic
          ? "bg-emerald-600 hover:bg-emerald-700 text-white"
          : "bg-primary text-primary-foreground",
        className
      )}
      aria-label={`Mark topic "${topicTitle || topicId}" complete`}
    >
      {isPending ? (
        <>
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          <span>Finalizing Topic...</span>
        </>
      ) : isLastTopic ? (
        <>
          <PartyPopper className="size-4" aria-hidden="true" />
          <span>Finish & Complete Subject</span>
        </>
      ) : (
        <>
          <CheckCircle2 className="size-4" aria-hidden="true" />
          <span>Mark Topic Complete & Continue</span>
        </>
      )}
    </Button>
  );
}
