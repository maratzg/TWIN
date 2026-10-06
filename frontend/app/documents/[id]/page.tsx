import { DocumentReview } from "@/components/DocumentReview";


export default async function DocumentPage({ params }: PageProps<"/documents/[id]">) {
  const { id } = await params;
  return <DocumentReview documentId={id}/>;
}

