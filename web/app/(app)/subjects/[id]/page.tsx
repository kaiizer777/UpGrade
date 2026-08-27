import { notFound, redirect } from "next/navigation";
import { getSubject } from "@/lib/api";

export default async function SubjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let subject;
  try {
    subject = await getSubject(id);
  } catch (err) {
    if (
      err &&
      typeof err === "object" &&
      "digest" in err &&
      typeof (err as { digest?: string }).digest === "string" &&
      ((err as { digest: string }).digest.startsWith("NEXT_REDIRECT") ||
        (err as { digest: string }).digest.startsWith("NEXT_NOT_FOUND"))
    ) {
      throw err;
    }
    notFound();
  }

  if (!subject) {
    notFound();
  }

  if (subject.onboarding_status === "ready") {
    redirect(`/subjects/${id}/roadmap`);
  } else {
    redirect(`/subjects/${id}/onboarding`);
  }
}
