import Link from "next/link";
import { ArrowRight, Zap } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { HeroSubjectInput } from "@/components/hero-subject-input";
import { cn } from "@/lib/utils";

export default function MarketingPage() {
  return (
    <div className="landing-page flex min-h-screen flex-col scrollbar-none">
      <style>{`
        html, body {
          -ms-overflow-style: none !important;
          scrollbar-width: none !important;
        }
        html::-webkit-scrollbar, body::-webkit-scrollbar {
          display: none !important;
        }
      `}</style>
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-8">
          <div className="flex items-center gap-2">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <Zap className="size-5" />
            </div>
            <span className="text-xl font-bold tracking-tight">UpGrade</span>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/subjects"
              className={cn(buttonVariants({ size: "sm" }))}
            >
              Manage Subjects
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main id="main-content" tabIndex={-1} className="flex-1 outline-none">
        <section className="relative mx-auto flex max-w-5xl flex-col items-center px-4 pt-20 pb-16 text-center sm:px-6 sm:pt-28 sm:pb-24">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/60 px-3.5 py-1 text-xs font-medium text-muted-foreground shadow-xs">
            <span className="flex size-1.5 rounded-full bg-emerald-500" />
            Next-Gen Learning Engine
          </div>

          <h1 className="mt-6 text-4xl font-extrabold tracking-tight sm:text-6xl sm:leading-[1.15]">
            Master Any Subject with{" "}
            <span className="bg-gradient-to-r from-primary to-muted-foreground bg-clip-text text-transparent">
              Just-in-Time Intelligence
            </span>
          </h1>

          {/* Premium Subject Input Bar */}
          <HeroSubjectInput placeholder="Enter your first subject... (e.g. Distributed Systems)" />

          <p className="mt-6 max-w-2xl text-base text-muted-foreground sm:text-lg">
            AI-generated personalized roadmaps, high-density bite-sized micro-feeds,
            and contextual topic chat. Skip the fluff and level up faster.
          </p>
        </section>
      </main>
    </div>
  );
}
