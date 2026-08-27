"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Plus, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { createSubject } from "@/lib/api";
import type { SubjectListItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const createSubjectSchema = z.object({
  title: z
    .string()
    .min(2, { message: "Title must be at least 2 characters long." })
    .max(100, { message: "Title cannot exceed 100 characters." }),
  description: z
    .string()
    .max(500, { message: "Description cannot exceed 500 characters." })
    .optional(),
});

export type CreateSubjectFormValues = z.infer<typeof createSubjectSchema>;

export interface CreateSubjectDialogProps {
  trigger?: React.ReactElement;
  onSuccess?: (subject: SubjectListItem) => void;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function CreateSubjectDialog({
  trigger,
  onSuccess,
  open: controlledOpen,
  onOpenChange: setControlledOpen,
}: CreateSubjectDialogProps) {
  const [internalOpen, setInternalOpen] = React.useState(false);
  const router = useRouter();

  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;
  const setOpen = (nextOpen: boolean) => {
    if (!isControlled) {
      setInternalOpen(nextOpen);
    }
    setControlledOpen?.(nextOpen);
  };

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateSubjectFormValues>({
    resolver: zodResolver(createSubjectSchema),
    defaultValues: {
      title: "",
      description: "",
    },
  });

  const handleFormSubmit = async (values: CreateSubjectFormValues) => {
    try {
      const newSubject = await createSubject({
        title: values.title.trim(),
        description: values.description?.trim() || null,
      });

      const listItem: SubjectListItem = {
        id: newSubject.id,
        title: newSubject.title,
        description: newSubject.description,
        created_at: newSubject.created_at,
        onboarding_status: "onboarding",
      };

      toast.success("Subject created!", {
        description: `Starting onboarding for "${newSubject.title}"`,
      });

      onSuccess?.(listItem);
      setOpen(false);
      reset();
      router.push(`/subjects/${newSubject.id}/onboarding`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to create subject";
      toast.error("Failed to create subject", {
        description: message,
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          trigger || (
            <Button size="default" className="gap-2">
              <Plus className="size-4" aria-hidden="true" />
              <span>Create Subject</span>
            </Button>
          )
        }
      />

      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
          <DialogHeader>
            <div className="flex items-center gap-2 text-primary">
              <Sparkles className="size-5" />
              <DialogTitle>Create Learning Subject</DialogTitle>
            </div>
            <DialogDescription>
              Enter a subject you want to master. We&apos;ll interview your goals
              and create a personalized roadmap.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Title Field */}
            <div className="space-y-1.5">
              <label
                htmlFor="subject-title"
                className="text-xs font-semibold tracking-wide text-foreground uppercase"
              >
                Subject Title <span className="text-destructive">*</span>
              </label>
              <Input
                id="subject-title"
                placeholder="e.g. Distributed Systems in Go, Quantum Computing..."
                autoFocus
                disabled={isSubmitting}
                aria-invalid={!!errors.title}
                aria-describedby={errors.title ? "title-error" : undefined}
                {...register("title")}
              />
              {errors.title && (
                <p id="title-error" className="text-xs text-destructive">
                  {errors.title.message}
                </p>
              )}
            </div>

            {/* Description Field */}
            <div className="space-y-1.5">
              <label
                htmlFor="subject-description"
                className="text-xs font-semibold tracking-wide text-foreground uppercase"
              >
                Description & Goals{" "}
                <span className="text-muted-foreground font-normal text-[11px]">
                  (Optional)
                </span>
              </label>
              <Textarea
                id="subject-description"
                placeholder="What specific skills or milestones do you want to achieve?"
                rows={3}
                disabled={isSubmitting}
                aria-invalid={!!errors.description}
                aria-describedby={
                  errors.description ? "description-error" : undefined
                }
                {...register("description")}
              />
              {errors.description && (
                <p
                  id="description-error"
                  className="text-xs text-destructive"
                >
                  {errors.description.message}
                </p>
              )}
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <DialogClose
              render={
                <Button
                  type="button"
                  variant="outline"
                  disabled={isSubmitting}
                  onClick={() => {
                    reset();
                    setOpen(false);
                  }}
                >
                  Cancel
                </Button>
              }
            />
            <Button type="submit" disabled={isSubmitting} className="gap-2">
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  <span>Creating...</span>
                </>
              ) : (
                <>
                  <Plus className="size-4" />
                  <span>Create Subject</span>
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
