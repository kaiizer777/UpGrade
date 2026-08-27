"use client";

import * as React from "react";
import { useSyncExternalStore } from "react";
import { RefreshCw, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface OfflineBannerProps {
  className?: string;
}

type OnlineStatus = "online" | "offline" | "reconnected";

let currentStatus: OnlineStatus = "online";
let reconnectedTimer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

if (typeof window !== "undefined") {
  window.addEventListener("offline", () => {
    if (reconnectedTimer) clearTimeout(reconnectedTimer);
    currentStatus = "offline";
    notify();
  });

  window.addEventListener("online", () => {
    currentStatus = "reconnected";
    notify();
    reconnectedTimer = setTimeout(() => {
      currentStatus = "online";
      notify();
    }, 4000);
  });
}

function subscribe(callback: () => void) {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
}

function getSnapshot(): OnlineStatus {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return "offline";
  }
  return currentStatus;
}

function getServerSnapshot(): OnlineStatus {
  return "online";
}

export function OfflineBanner({ className }: OfflineBannerProps) {
  const status = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot
  );

  if (status === "online") {
    return null;
  }

  if (status === "reconnected") {
    return (
      <div
        role="status"
        aria-live="polite"
        className={cn(
          "w-full bg-emerald-600 text-white px-4 py-2 text-xs font-medium transition-all duration-300 animate-in slide-in-from-top flex items-center justify-center gap-2 shadow-xs",
          className
        )}
      >
        <Wifi className="size-3.5 shrink-0" />
        <span>Connection restored. You are back online!</span>
      </div>
    );
  }

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "w-full bg-amber-600 dark:bg-amber-700 text-white px-4 py-2 text-xs font-medium transition-all duration-300 animate-in slide-in-from-top flex flex-wrap items-center justify-between gap-2 shadow-sm",
        className
      )}
    >
      <div className="flex items-center gap-2">
        <WifiOff className="size-4 shrink-0" />
        <span>
          You are currently offline. AI generation and updates are paused until connection is restored.
        </span>
      </div>

      <Button
        type="button"
        size="xs"
        variant="secondary"
        onClick={() => {
          if (typeof window !== "undefined") {
            window.dispatchEvent(
              new Event(navigator.onLine ? "online" : "offline")
            );
          }
        }}
        className="h-6 text-[11px] bg-white/20 hover:bg-white/30 text-white border-0 shadow-none gap-1"
      >
        <RefreshCw className="size-3" />
        Check connection
      </Button>
    </div>
  );
}
