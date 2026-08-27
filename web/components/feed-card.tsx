"use client";

import * as React from "react";
import { MessageSquare, Sparkles, Terminal } from "lucide-react";
import type { FeedPostRead } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface FeedCardProps {
  post: FeedPostRead;
  totalPosts?: number;
  topicTitle?: string;
  onOpenChat?: (post: FeedPostRead) => void;
  className?: string;
}

/**
 * Format post content with code block detection and inline formatting.
 */
function FormattedPostContent({ content }: { content: string }) {
  // Check for triple-backtick code blocks
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    const textBefore = content.slice(lastIndex, match.index);
    if (textBefore) {
      parts.push(
        <span key={`text-${lastIndex}`} className="whitespace-pre-wrap leading-relaxed">
          {textBefore}
        </span>
      );
    }

    const lang = match[1] || "";
    const code = match[2]?.trim() || "";

    parts.push(
      <div
        key={`code-${match.index}`}
        className="my-3 overflow-hidden rounded-lg border border-border/80 bg-muted/70 font-mono text-xs shadow-xs"
      >
        {lang && (
          <div className="flex items-center justify-between border-b border-border/60 bg-muted px-3 py-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
            <span className="flex items-center gap-1">
              <Terminal className="size-3" />
              {lang}
            </span>
          </div>
        )}
        <pre className="overflow-x-auto p-3 text-foreground selection:bg-primary/20">
          <code>{code}</code>
        </pre>
      </div>
    );

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    const textRemaining = content.slice(lastIndex);
    parts.push(
      <span key={`text-${lastIndex}`} className="whitespace-pre-wrap leading-relaxed">
        {textRemaining}
      </span>
    );
  }

  if (parts.length === 0) {
    return <p className="whitespace-pre-wrap leading-relaxed text-sm text-foreground/90">{content}</p>;
  }

  return <div className="text-sm text-foreground/90 space-y-1">{parts}</div>;
}

export function FeedCard({
  post,
  totalPosts,
  topicTitle,
  onOpenChat,
  className,
}: FeedCardProps) {
  const postNumber = post.order_index + 1;
  const totalDisplay = totalPosts ? ` / ${totalPosts}` : "";

  return (
    <Card
      tabIndex={0}
      className={cn(
        "group relative flex flex-col rounded-xl border border-border/80 bg-card shadow-xs transition-all duration-200 hover:border-primary/40 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className
      )}
      aria-label={`Feed post ${postNumber}${totalPosts ? ` of ${totalPosts}` : ""}`}
    >
      {/* Header: Index badge and metadata */}
      <CardHeader className="flex flex-row items-center justify-between space-y-0 px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <span className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
            {postNumber}
          </span>
          <span className="text-xs font-medium text-muted-foreground">
            Post {postNumber}{totalDisplay}
          </span>
        </div>

        <div className="flex items-center gap-1 text-[11px] text-muted-foreground/80 font-mono">
          <Sparkles className="size-3 text-amber-500/80" aria-hidden="true" />
          <span>Bite-sized</span>
        </div>
      </CardHeader>

      {/* Main Lesson Content */}
      <CardContent className="px-4 py-2">
        <FormattedPostContent content={post.content} />
      </CardContent>

      {/* Footer: Open Chat Doubts action */}
      <CardFooter className="flex items-center justify-between border-t border-border/50 bg-muted/20 px-4 py-2.5">
        <div className="text-[11px] text-muted-foreground truncate max-w-[200px] sm:max-w-xs">
          {topicTitle ? `${topicTitle}` : "Active Topic"}
        </div>

        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => onOpenChat?.(post)}
          className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-background/80 transition-colors focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={`Open doubts chat for post ${postNumber}`}
        >
          <MessageSquare className="size-3.5 text-primary" aria-hidden="true" />
          <span>Open Chat</span>
        </Button>
      </CardFooter>
    </Card>
  );
}
