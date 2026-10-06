import { BillOfLadingDetail } from "@/components/BillOfLadingDetail";

export default async function BillOfLadingPage({ params }: PageProps<"/bills-of-lading/[id]">) {
  const { id } = await params;
  return <BillOfLadingDetail billId={id}/>;
}
