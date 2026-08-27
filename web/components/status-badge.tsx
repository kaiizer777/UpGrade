import * as React from "react";
import { CheckCircle2, Circle, Clock, PlayCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export type StatusBadgeVariant =
  | "onboarding"
  | "ready"
  | "pending"
  | "active"
  | "done"
  | (string & {});

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: StatusBadgeVariant;
  showIcon?: boolean;
  size?: "sm" | "default";
}

interface StatusConfig {
  label: string;
  className: string;
  icon: React.ComponentType<{ className?: string }>;
}

const STATUS_CONFIGS: Record<string, StatusConfig> = {
  onboarding: {
    label: "Onboarding",
    className:
      "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    icon: Clock,
  },
  ready: {
    label: "Ready",
    className:
      "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    icon: CheckCircle2,
  },
  pending: {
    label: "Pending",
    className: "bg-muted/80 text-muted-foreground border-border",
    icon: Circle,
  },
  active: {
    label: "Active",
    className:
      "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
    icon: PlayCircle,
  },
  done: {
    label: "Done",
    className:
      "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    icon: CheckCircle2,
  },
};

const DEFAULT_CONFIG: StatusConfig = {
  label: "Unknown",
  className: "bg-muted text-muted-foreground border-border",
  icon: Circle,
};

export function StatusBadge({
  status,
  showIcon = true,
  size = "default",
  className,
  ...props
}: StatusBadgeProps) {
  const normalizedStatus = (status || "").toLowerCase();
  const config = STATUS_CONFIGS[normalizedStatus] || {
    ...DEFAULT_CONFIG,
    label: status || "Unknown",
  };
  const Icon = config.icon;

  return (
    <span
      role="status"
      aria-label={`Status: ${config.label}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium capitalize select-none transition-colors",
        size === "sm"
          ? "px-2 py-0.5 text-[11px] leading-none"
          : "px-2.5 py-1 text-xs leading-none",
        config.className,
        className
      )}
      {...props}
    >
      {showIcon && (
        <Icon
          className={cn(
            "shrink-0",
            size === "sm" ? "size-2.5" : "size-3"
          )}
          aria-hidden="true"
        />
      )}
      <span>{config.label}</span>
    </span>
  );
}
