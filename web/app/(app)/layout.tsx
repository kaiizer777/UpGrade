import * as React from "react";
import { AppNav } from "@/components/app-nav";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground selection:bg-primary/10">
      <AppNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-7xl flex-1 flex-col px-3 py-6 sm:px-6 lg:px-8 outline-none"
      >
        <React.Suspense
          fallback={
            <div
              className="w-full flex-1 animate-pulse"
              aria-label="Loading content"
            />
          }
        >
          {children}
        </React.Suspense>
      </main>
    </div>
  );
}
