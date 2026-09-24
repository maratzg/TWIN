"use client";

import { useParams } from "next/navigation";
import { ImportReviewWorkbench } from "@/components/ImportReviewWorkbench";

export default function ImportDetailPage() {
  const params = useParams<{ id: string }>();
  return <ImportReviewWorkbench importId={params.id} />;
}

