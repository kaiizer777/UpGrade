import * as React from "react";
import { Suspense } from "react";
import { SubjectSwitcher } from "@/components/subject-switcher";
import { Skeleton } from "@/components/ui/skeleton";

function SwitcherFallback() {
  return (
    <div className="flex items-center gap-2 overflow-hidden py-1">
      <Skeleton className="h-8 w-28 rounded-full" />
      <Skeleton className="h-8 w-36 rounded-full" />
      <Skeleton className="h-8 w-24 rounded-full" />
    </div>
  );
}

export default function SubjectsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-6">
      {/* Subject Switcher Bar */}
      <section
        aria-label="Subject navigation"
        className="flex items-center justify-between gap-4 border-b border-border/60 pb-3"
      >
        <div className="flex-1 min-w-0">
          <Suspense fallback={<SwitcherFallback />}>
            <SubjectSwitcher />
          </Suspense>
        </div>
      </section>

      {/* Segment Content */}
      <div className="flex-1">
        <Suspense
          fallback={
            <div className="space-y-4 py-4">
              <Skeleton className="h-8 w-64" />
              <Skeleton className="h-24 w-full rounded-xl" />
              <Skeleton className="h-48 w-full rounded-xl" />
            </div>
          }
        >
          {children}
        </Suspense>
      </div>
    </div>
  );
}
