import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import type { TrendSeries } from "../../api/types";
import { LabChart } from "../../components/charts";
import { Card, EmptyState, ErrorState, Notice, Skeleton, StatusChip, day } from "../../components/ui";
import { HealthProps, STATUS_LABEL, STATUS_TONE } from "./shared";

const ARROW = { rising: "↗ Rising", falling: "↘ Falling", stable: "→ Stable", unknown: "—" } as const;

export default function TrendsTab({ base }: HealthProps) {
  const [selected, setSelected] = useState("");
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["trends", base], queryFn: () => api<TrendSeries[]>(`${base}/trends`) });
  if (isLoading) return <Skeleton lines={6} height={22} />;
  if (error || !data) return <ErrorState error={error} retry={() => void refetch()} />;
  if (data.length === 0) return <EmptyState title="No results to chart yet">Add a check-up on the Labs tab. Trends appear once a measurement has at least two results.</EmptyState>;
  const current = data.find((s) => s.key === selected) ?? data.find((s) => s.points.length > 1) ?? data[0];
  const alerts = data.filter((s) => s.alert);
  return (
    <div className="stack">
      {alerts.length > 0 && (
        <Notice tone="warn" title="Trends worth discussing with a doctor">
          <ul>{alerts.map((s) => <li key={s.key}>{s.alert?.message}</li>)}</ul>
          <p className="muted small">A trend is a pattern in your own results, not a diagnosis.</p>
        </Notice>
      )}
      <Card title={current.label} action={
        <select aria-label="Measurement" value={current.key} onChange={(e) => setSelected(e.target.value)}>
          {data.map((s) => <option key={s.key} value={s.key}>{s.label}{s.points.length > 1 ? "" : " (1 result)"}</option>)}
        </select>}>
        {current.points.length < 2 ? <EmptyState title="Add one more result to see a trend" /> : <LabChart series={current} />}
        <p className="muted small">The shaded band is the typical adult range{current.low !== null ? ` (${current.low} to ${current.high} ${current.unit})` : ""}. Your laboratory&apos;s range may differ.</p>
      </Card>
      <div className="cards three">
        {data.map((s) => (
          <button key={s.key} className={`card trend-card ${s.key === current.key ? "on" : ""}`} onClick={() => setSelected(s.key)}>
            <span className="stat-label">{s.label}</span>
            <span className="stat-value">{s.latest} <small>{s.unit}</small></span>
            <span className="row"><StatusChip tone={STATUS_TONE[s.status]} label={STATUS_LABEL[s.status]} /><span className="muted small">{ARROW[s.direction]}</span></span>
            <span className="muted small">{s.points.length} result{s.points.length === 1 ? "" : "s"}{s.latest_date ? ` · latest ${day(`${s.latest_date}T12:00:00`)}` : ""}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
