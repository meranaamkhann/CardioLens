import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import type { HealthAlertRow } from "../../api/types";
import { useToast } from "../../components/Toast";
import { Card, EmptyState, ErrorState, Skeleton, StatusChip, when } from "../../components/ui";
import { HealthProps, SEVERITY_TONE } from "./shared";

export default function AlertsTab({ base }: HealthProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [all, setAll] = useState(false);
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["alerts", base, all], queryFn: () => api<HealthAlertRow[]>(`${base}/alerts?include=${all ? "all" : "open"}`) });
  const ack = useMutation({
    mutationFn: (id: number) => api(`${base}/alerts/${id}/acknowledge`, { method: "POST" }),
    onSuccess: () => { toast.success("Marked as seen."); for (const k of ["alerts", "summary", "dashboard"]) void queryClient.invalidateQueries({ queryKey: [k] }); },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not update."),
  });
  if (isLoading) return <Skeleton lines={4} height={24} />;
  if (error || !data) return <ErrorState error={error} retry={() => void refetch()} />;
  return (
    <Card title="Health alerts" action={<label className="check small"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /><span>Show resolved</span></label>}>
      <p className="muted">Alerts come from comparing results with typical ranges and from steady trends. They are prompts to talk to a doctor, never a diagnosis.</p>
      {data.length === 0 ? <EmptyState title="No open alerts">Nothing needs attention right now.</EmptyState> : (
        <ul className="list">
          {data.map((a) => (
            <li key={a.id} className={`alert-row ${a.severity}`}>
              <div>
                <div className="row"><StatusChip tone={SEVERITY_TONE[a.severity]} label={a.severity === "critical" ? "Critical" : a.severity === "warning" ? "Warning" : "Note"} />
                  <span className="muted small">{a.kind === "trend" ? "Trend" : "Result"} · {when(a.created_at)}{a.resolved ? " · resolved" : ""}</span></div>
                <p>{a.message}</p>
              </div>
              {!a.resolved && !a.acknowledged && <button className="btn ghost small" onClick={() => ack.mutate(a.id)}>Mark as seen</button>}
              {a.acknowledged && <span className="muted small">Seen</span>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
