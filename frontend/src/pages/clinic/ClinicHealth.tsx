import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { HealthAlertRow, OverdueRow } from "../../api/types";
import { useToast } from "../../components/Toast";
import { Card, EmptyState, ErrorState, Skeleton, StatusChip, when } from "../../components/ui";
import { SEVERITY_TONE } from "../health/shared";

export default function ClinicHealth() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const alerts = useQuery({ queryKey: ["clinic-alerts"], queryFn: () => api<HealthAlertRow[]>("/clinic/health/alerts"), refetchInterval: 60_000 });
  const overdue = useQuery({ queryKey: ["clinic-overdue"], queryFn: () => api<OverdueRow[]>("/clinic/health/overdue") });
  const ack = useMutation({
    mutationFn: (a: HealthAlertRow) => api(`/clinic/patients/${a.patient_id}/health/alerts/${a.id}/acknowledge`, { method: "POST" }),
    onSuccess: () => { toast.success("Alert acknowledged."); void queryClient.invalidateQueries({ queryKey: ["clinic-alerts"] }); },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not acknowledge."),
  });
  return (
    <div className="stack">
      <div><h1>Alerts and reminders</h1><p className="muted">Lab-result alerts and overdue check-ups for patients who share their records with your clinic.</p></div>
      <Card title="Open lab alerts">
        {alerts.isLoading ? <Skeleton lines={4} /> : alerts.error || !alerts.data ? <ErrorState error={alerts.error} retry={() => void alerts.refetch()} /> : alerts.data.length === 0 ? <EmptyState title="No open alerts" /> : (
          <ul className="list">
            {alerts.data.map((a) => (
              <li key={a.id} className={`alert-row ${a.severity}`}>
                <div><div className="row"><StatusChip tone={SEVERITY_TONE[a.severity]} label={a.severity} /><Link to={`/clinic/patients/${a.patient_id}`}><strong>{a.patient_name}</strong></Link><span className="muted small">{when(a.created_at)}</span></div>
                  <p>{a.message}</p></div>
                <button className="btn ghost small" onClick={() => ack.mutate(a)}>Acknowledge</button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Overdue check-ups">
        {overdue.isLoading ? <Skeleton lines={3} /> : overdue.error || !overdue.data ? <ErrorState error={overdue.error} /> : overdue.data.length === 0 ? <EmptyState title="Everyone is up to date" /> : (
          <ul className="list">
            {overdue.data.map((o) => (
              <li key={o.patient_id}><div><Link to={`/clinic/patients/${o.patient_id}`}><strong>{o.patient_name}</strong></Link>
                <span className="muted small">{o.days_since === null ? "No check-up recorded" : `Last check-up ${o.days_since} days ago`}</span></div></li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
