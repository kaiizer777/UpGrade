"use client";

import * as React from "react";
import { Sparkles } from "lucide-react";
import type { FeedPostRead } from "@/lib/types";
import { useMediaQuery } from "@/hooks/use-media-query";
import { ChatPanel } from "@/components/chat-panel";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

export interface ChatSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subjectId: string;
  topicId: number;
  topicTitle?: string;
  initialPost?: FeedPostRead | null;
}

export function ChatSheet({
  open,
  onOpenChange,
  subjectId,
  topicId,
  topicTitle,
  initialPost,
}: ChatSheetProps) {
  // Use Dialog on desktop (lg: >= 1024px) and Sheet on mobile/tablet
  const isDesktop = useMediaQuery("(min-width: 1024px)");

  // Shared Header Content
  const headerContent = (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2 text-primary">
        <Sparkles className="size-4 text-amber-500" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wider">
          Topic Doubts & Clarification
        </span>
      </div>
      <span className="font-heading text-lg font-bold text-foreground line-clamp-1">
        {topicTitle || "Active Topic"}
      </span>
      <span className="text-xs text-muted-foreground">
        AI-assisted discussions scoped to this lesson.
      </span>
    </div>
  );

  const panel = (
    <ChatPanel
      subjectId={subjectId}
      topicId={topicId}
      topicTitle={topicTitle}
      initialPost={initialPost}
      onClose={() => onOpenChange(false)}
      className="flex-1"
    />
  );

  if (isDesktop) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex h-[85vh] max-h-[850px] w-full max-w-3xl flex-col gap-0 overflow-hidden p-0 rounded-2xl border border-border/80 bg-background shadow-2xl">
          <DialogHeader className="shrink-0 border-b border-border/80 p-5 bg-card/60">
            <DialogTitle className="sr-only">
              {topicTitle ? `Doubts for ${topicTitle}` : "Topic Doubts"}
            </DialogTitle>
            <DialogDescription className="sr-only">
              Ask any doubts or questions related to this topic.
            </DialogDescription>
            {headerContent}
          </DialogHeader>
          {panel}
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex h-full w-full flex-col gap-0 overflow-hidden p-0 border-l border-border bg-background sm:max-w-md"
      >
        <SheetHeader className="shrink-0 border-b border-border/80 p-4 bg-card/60">
          <SheetTitle className="sr-only">
            {topicTitle ? `Doubts for ${topicTitle}` : "Topic Doubts"}
          </SheetTitle>
          <SheetDescription className="sr-only">
            Ask any doubts or questions related to this topic.
          </SheetDescription>
          {headerContent}
        </SheetHeader>
        {panel}
      </SheetContent>
    </Sheet>
  );
}
