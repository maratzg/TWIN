import { ShipmentDetailView } from "@/components/ShipmentDetailView";

export default async function ShipmentDetailPage({ params }: PageProps<"/shipments/[id]">) {
  const { id } = await params;
  return <ShipmentDetailView shipmentId={id}/>;
}
