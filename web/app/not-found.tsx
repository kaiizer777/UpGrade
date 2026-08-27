import Link from "next/link";
import { ArrowLeft, Compass } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export default function NotFound() {
  return (
    <div className="flex min-h-[70vh] items-center justify-center p-4 sm:p-8">
      <Card className="w-full max-w-md text-center shadow-lg">
        <CardHeader className="space-y-2">
          <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Compass className="size-6" />
          </div>
          <CardTitle className="text-2xl font-bold">404 - Page Not Found</CardTitle>
          <CardDescription className="text-sm text-muted-foreground">
            The page you are looking for doesn&apos;t exist or has been moved.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          Double-check the URL or jump back into your learning subjects.
        </CardContent>
        <CardFooter className="flex justify-center gap-3">
          <Link
            href="/subjects"
            className={cn(buttonVariants({ size: "default" }), "gap-2")}
          >
            <ArrowLeft className="size-4" />
            Go to Subjects
          </Link>
          <Link
            href="/"
            className={cn(buttonVariants({ variant: "outline", size: "default" }))}
          >
            Home
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}
