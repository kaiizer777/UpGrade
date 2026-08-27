"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { prefetchTopic } from "@/lib/api";

export interface UsePrefetchOptions {
  subjectId: string;
  nextTopicId?: number | null;
  /**
   * Intersection threshold (0.0 to 1.0). Defaults to 0.7 (70%).
   */
  threshold?: number;
  /**
   * Whether prefetching is active. Defaults to true.
   */
  enabled?: boolean;
  onPrefetchSuccess?: (topicId: number) => void;
  onPrefetchError?: (topicId: number, error: unknown) => void;
}

export interface UsePrefetchReturn {
  targetRef: (node: HTMLElement | null) => void;
  triggerPrefetch: (topicId: number) => Promise<void>;
  hasPrefetched: boolean;
}

/**
 * Hook to trigger background prefetching of the next roadmap topic when the user
 * reaches ~70% scroll depth through the current active topic's feed.
 *
 * Features:
 * - IntersectionObserver with threshold 0.7
 * - Deduped Set tracking to prevent duplicate network calls
 * - Non-blocking background execution with graceful fallback
 */
export function usePrefetch({
  subjectId,
  nextTopicId,
  threshold = 0.7,
  enabled = true,
  onPrefetchSuccess,
  onPrefetchError,
}: UsePrefetchOptions): UsePrefetchReturn {
  const [prefetchedTopics, setPrefetchedTopics] = useState<Set<number>>(() => new Set<number>());
  const prefetchedSetRef = useRef<Set<number>>(new Set<number>());
  const observerRef = useRef<IntersectionObserver | null>(null);
  const targetElementRef = useRef<HTMLElement | null>(null);

  const triggerPrefetch = useCallback(
    async (topicId: number) => {
      if (!subjectId || prefetchedSetRef.current.has(topicId)) {
        return;
      }
      // Optimistically record in Set to prevent concurrent duplicate calls
      prefetchedSetRef.current.add(topicId);
      setPrefetchedTopics((prev) => {
        const next = new Set(prev);
        next.add(topicId);
        return next;
      });

      try {
        await prefetchTopic(subjectId, topicId);
        onPrefetchSuccess?.(topicId);
      } catch (err) {
        // Non-blocking fallback; log warning and continue without breaking UI
        console.warn(
          `[usePrefetch] Background JIT prefetch failed for topic ${topicId}:`,
          err
        );
        onPrefetchError?.(topicId, err);
      }
    },
    [subjectId, onPrefetchSuccess, onPrefetchError]
  );

  const setTargetRef = useCallback(
    (node: HTMLElement | null) => {
      // Disconnect existing observer if target changes
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }

      targetElementRef.current = node;

      if (!node || !enabled || !nextTopicId || prefetchedSetRef.current.has(nextTopicId)) {
        return;
      }

      if (typeof window === "undefined" || !("IntersectionObserver" in window)) {
        // Fallback for environments lacking IntersectionObserver
        triggerPrefetch(nextTopicId);
        return;
      }

      const observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            // Trigger when reaching 70% threshold
            if (entry.isIntersecting && entry.intersectionRatio >= threshold) {
              triggerPrefetch(nextTopicId);
              observer.disconnect();
              break;
            }
          }
        },
        {
          threshold: [threshold],
        }
      );

      observer.observe(node);
      observerRef.current = observer;
    },
    [enabled, nextTopicId, threshold, triggerPrefetch]
  );

  useEffect(() => {
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, []);

  const hasPrefetched = nextTopicId ? prefetchedTopics.has(nextTopicId) : false;

  return {
    targetRef: setTargetRef,
    triggerPrefetch,
    hasPrefetched,
  };
}
