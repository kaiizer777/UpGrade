"use client";

import * as React from "react";
import { AlertOctagon, BookOpen, Plus, RefreshCw, Sparkles } from "lucide-react";
import { useSubject } from "@/hooks/use-subject";
import { SubjectCard } from "@/components/subject-card";
import { CreateSubjectDialog } from "@/components/create-subject-dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import SubjectsLoading from "@/app/(app)/subjects/loading";

export default function SubjectsPage() {
  const {
    subjects,
    selectedSubjectId,
    selectSubject,
    isLoading,
    error,
    refreshSubjects,
    addOptimisticSubject,
  } = useSubject();

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/60 pb-5">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Learning Subjects
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your learning tracks, follow custom roadmaps, and level up.
          </p>
        </div>

        <CreateSubjectDialog
          onSuccess={addOptimisticSubject}
          trigger={
            <Button className="gap-2 shadow-xs">
              <Plus className="size-4" aria-hidden="true" />
              <span>Create Subject</span>
            </Button>
          }
        />
      </div>

      {/* Loading State */}
      {isLoading && <SubjectsLoading />}

      {/* Error State */}
      {!isLoading && error && (
        <Card className="border-destructive/30 bg-destructive/5 text-center p-6 sm:p-8">
          <CardHeader className="space-y-2">
            <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <AlertOctagon className="size-6" />
            </div>
            <CardTitle className="text-xl text-destructive">
              Failed to Load Subjects
            </CardTitle>
            <CardDescription className="max-w-md mx-auto">
              {error}
            </CardDescription>
          </CardHeader>
          <CardFooter className="justify-center pt-2">
            <Button
              onClick={() => refreshSubjects()}
              variant="outline"
              className="gap-2"
            >
              <RefreshCw className="size-4" />
              <span>Try Again</span>
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Empty State */}
      {!isLoading && !error && subjects.length === 0 && (
        <Card className="border-dashed border-2 p-8 sm:p-12 text-center bg-card/40">
          <CardHeader className="space-y-3">
            <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary">
              <BookOpen className="size-7" />
            </div>
            <CardTitle className="text-2xl font-bold tracking-tight">
              No subjects created yet
            </CardTitle>
            <CardDescription className="max-w-md mx-auto text-sm text-muted-foreground">
              Kickstart your learning journey by creating your first subject. Our AI
              interviewer will tailor a high-impact roadmap for you.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-2">
            <CreateSubjectDialog
              onSuccess={addOptimisticSubject}
              trigger={
                <Button size="lg" className="gap-2 shadow-xs">
                  <Sparkles className="size-4" />
                  <span>Create Your First Subject</span>
                </Button>
              }
            />
          </CardContent>
        </Card>
      )}

      {/* Subject Grid */}
      {!isLoading && !error && subjects.length > 0 && (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {subjects.map((subject) => (
            <SubjectCard
              key={subject.id}
              subject={subject}
              isSelected={subject.id === selectedSubjectId}
              onSelect={selectSubject}
            />
          ))}
        </div>
      )}
    </div>
  );
}
