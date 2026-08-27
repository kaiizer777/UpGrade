"use client";

import * as React from "react";
import { AlertCircle, RefreshCw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ErrorBannerProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}

export function ErrorBanner({
  title = "Something went wrong",
  message,
  onRetry,
  onDismiss,
  className,
  ...props
}: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        "relative flex flex-col gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-destructive shadow-xs sm:flex-row sm:items-center sm:justify-between",
        className
      )}
      {...props}
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 size-5 shrink-0 text-destructive" />
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-semibold leading-none tracking-tight text-foreground">
            {title}
          </p>
          <p className="text-xs text-muted-foreground">{message}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 self-end sm:self-center">
        {onRetry && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="h-8 gap-1.5 border-destructive/30 bg-background text-xs text-foreground hover:bg-destructive/10"
          >
            <RefreshCw className="size-3.5" />
            Retry
          </Button>
        )}
        {onDismiss && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onDismiss}
            aria-label="Dismiss error"
            className="size-8 text-muted-foreground hover:text-foreground"
          >
            <X className="size-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
