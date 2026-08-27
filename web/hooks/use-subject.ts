"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { getSubjects } from "@/lib/api";
import type { SubjectListItem } from "@/lib/types";

const STORAGE_KEY = "upgrade_active_subject_id";

export interface UseSubjectReturn {
  subjects: SubjectListItem[];
  selectedSubjectId: string | null;
  selectedSubject: SubjectListItem | null;
  isLoading: boolean;
  error: string | null;
  selectSubject: (id: string | null) => void;
  refreshSubjects: () => Promise<void>;
  addOptimisticSubject: (subject: SubjectListItem) => void;
}

export function useSubject(): UseSubjectReturn {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [subjects, setSubjects] = useState<SubjectListItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const urlSubjectId = searchParams.get("subject");

  // Load initial subjects
  useEffect(() => {
    let isMounted = true;

    getSubjects()
      .then((data) => {
        if (isMounted) {
          setSubjects(data);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          const message =
            err instanceof Error ? err.message : "Failed to load subjects";
          setError(message);
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Manual refresh helper
  const refreshSubjects = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getSubjects();
      setSubjects(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load subjects";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Determine active subject ID
  const selectedSubjectId = useMemo(() => {
    if (urlSubjectId) {
      return urlSubjectId;
    }
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && subjects.some((s) => s.id === saved)) {
        return saved;
      }
    }
    if (subjects.length > 0) {
      return subjects[0].id;
    }
    return null;
  }, [urlSubjectId, subjects]);

  // Sync to localStorage and URL if needed
  useEffect(() => {
    if (selectedSubjectId) {
      if (typeof window !== "undefined") {
        localStorage.setItem(STORAGE_KEY, selectedSubjectId);
      }
      // If URL doesn't have the subject param yet, sync it
      if (!urlSubjectId && pathname.startsWith("/subjects")) {
        const params = new URLSearchParams(searchParams.toString());
        params.set("subject", selectedSubjectId);
        router.replace(`${pathname}?${params.toString()}`, { scroll: false });
      }
    }
  }, [selectedSubjectId, urlSubjectId, pathname, searchParams, router]);

  const selectSubject = useCallback(
    (id: string | null) => {
      if (typeof window !== "undefined") {
        if (id) {
          localStorage.setItem(STORAGE_KEY, id);
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
      }
      const params = new URLSearchParams(searchParams.toString());
      if (id) {
        params.set("subject", id);
      } else {
        params.delete("subject");
      }
      const queryString = params.toString();
      const newUrl = queryString ? `${pathname}?${queryString}` : pathname;
      router.push(newUrl, { scroll: false });
    },
    [pathname, searchParams, router]
  );

  const selectedSubject = useMemo(
    () => subjects.find((s) => s.id === selectedSubjectId) ?? null,
    [subjects, selectedSubjectId]
  );

  const addOptimisticSubject = useCallback((newSubject: SubjectListItem) => {
    setSubjects((prev) => [
      newSubject,
      ...prev.filter((s) => s.id !== newSubject.id),
    ]);
  }, []);

  return {
    subjects,
    selectedSubjectId,
    selectedSubject,
    isLoading,
    error,
    selectSubject,
    refreshSubjects,
    addOptimisticSubject,
  };
}
