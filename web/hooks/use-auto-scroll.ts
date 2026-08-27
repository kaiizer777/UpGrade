"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface UseAutoScrollOptions {
  /**
   * Distance from bottom in px to consider user "at bottom".
   * Defaults to 80.
   */
  threshold?: number;
  /**
   * Scroll behavior. Defaults to "smooth".
   */
  behavior?: ScrollBehavior;
  /**
   * Whether auto-scrolling is enabled. Defaults to true.
   */
  enabled?: boolean;
}

export interface UseAutoScrollReturn<T extends HTMLElement = HTMLDivElement> {
  scrollRef: React.RefObject<T | null>;
  bottomRef: React.RefObject<HTMLDivElement | null>;
  isAtBottom: boolean;
  scrollToBottom: (customBehavior?: ScrollBehavior) => void;
  handleScroll: () => void;
}

/**
 * Hook to manage intelligent auto-scrolling for dynamic chat, onboarding streams, and feeds.
 * Pauses auto-scroll when user manually scrolls up, resumes when scrolled back to bottom.
 */
export function useAutoScroll<T extends HTMLElement = HTMLDivElement>(
  dependencies: unknown[] = [],
  options: UseAutoScrollOptions = {}
): UseAutoScrollReturn<T> {
  const { threshold = 80, behavior = "smooth", enabled = true } = options;

  const scrollRef = useRef<T | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [isAtBottom, setIsAtBottom] = useState<boolean>(true);

  // Check if prefers-reduced-motion is active
  const getEffectiveBehavior = useCallback(
    (requestedBehavior?: ScrollBehavior): ScrollBehavior => {
      if (
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ) {
        return "auto";
      }
      return requestedBehavior || behavior;
    },
    [behavior]
  );

  const scrollToBottom = useCallback(
    (customBehavior?: ScrollBehavior) => {
      const effBehavior = getEffectiveBehavior(customBehavior);
      if (bottomRef.current) {
        bottomRef.current.scrollIntoView({ behavior: effBehavior, block: "end" });
      } else if (scrollRef.current) {
        scrollRef.current.scrollTo({
          top: scrollRef.current.scrollHeight,
          behavior: effBehavior,
        });
      }
    },
    [getEffectiveBehavior]
  );

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;

    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distanceFromBottom <= threshold;
    setIsAtBottom(atBottom);
  }, [threshold]);

  // Automatically scroll when dependencies change if enabled and user is at bottom
  useEffect(() => {
    if (!enabled) return;

    if (isAtBottom) {
      scrollToBottom();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);

  return {
    scrollRef,
    bottomRef,
    isAtBottom,
    scrollToBottom,
    handleScroll,
  };
}
