import { Badge } from "@/components/ui/badge";
import type { RunStatus } from "@/lib/types";

const VARIANT: Record<RunStatus, "info" | "warning" | "success" | "destructive" | "secondary"> = {
  pending: "secondary",
  running: "warning",
  succeeded: "success",
  failed: "destructive",
  cancelled: "secondary",
};

const LABEL: Record<RunStatus, string> = {
  pending: "Pending",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return <Badge variant={VARIANT[status] || "secondary"}>{LABEL[status] || status}</Badge>;
}
