import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, download } from "../../api/client";
import type { BiomarkerCatalogue, CheckupRow } from "../../api/types";
import { useToast } from "../../components/Toast";
import { Card, EmptyState, ErrorState, Field, Notice, Skeleton, StatusChip, when } from "../../components/ui";
import { HealthProps, STATUS_LABEL, STATUS_TONE, today } from "./shared";

export default function LabsTab({ base, viewer }: HealthProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [date, setDate] = useState(today());
  const [values, setValues] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const [open, setOpen] = useState<string>("vitals");
  const [error, setError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const catalogue = useQuery({ queryKey: ["biomarkers", base], queryFn: () => api<BiomarkerCatalogue>(`${base}/biomarkers`) });
  const history = useQuery({ queryKey: ["checkups", base], queryFn: () => api<CheckupRow[]>(`${base}/checkups`) });
  const refresh = () => {
    for (const k of ["checkups", "trends", "alerts", "summary", "dashboard"]) void queryClient.invalidateQueries({ queryKey: [k] });
  };

  const add = useMutation({
    mutationFn: (body: { checkup_date: string; values: Record<string, number>; notes: string | null }) => api<CheckupRow>(`${base}/checkups`, { method: "POST", body }),
    onSuccess: () => { setValues({}); setNotes(""); setError(""); toast.success("Check-up saved."); refresh(); },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not save."),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`${base}/checkups/${id}`, { method: "DELETE" }),
    onSuccess: () => { toast.success("Check-up deleted."); refresh(); },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not delete."),
  });
  const upload = useMutation({
    mutationFn: () => { const form = new FormData(); form.append("file", file as File); return api<{ imported: number }>(`${base}/import/checkups-csv`, { method: "POST", form }); },
    onSuccess: (r) => { setFile(null); toast.success(`${r.imported} check-up${r.imported === 1 ? "" : "s"} imported.`); refresh(); },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Import failed."),
  });

  if (catalogue.isLoading) return <Skeleton lines={6} height={22} />;
  if (catalogue.error || !catalogue.data) return <ErrorState error={catalogue.error} retry={() => void catalogue.refetch()} />;
  const info = new Map(catalogue.data.biomarkers.map((b) => [b.key, b]));

  const submit = () => {
    const entered: Record<string, number> = {};
    for (const [key, raw] of Object.entries(values)) {
      if (raw.trim() === "") continue;
      const marker = info.get(key);
      const n = Number(raw);
      if (!marker || Number.isNaN(n)) return setError(`${marker?.label ?? key} must be a number.`);
      if (n < marker.plausible[0] || n > marker.plausible[1]) return setError(`${marker.label} must be between ${marker.plausible[0]} and ${marker.plausible[1]} ${marker.unit}.`);
      entered[key] = n;
    }
    if (Object.keys(entered).length === 0) return setError("Enter at least one measurement.");
    if (date > today()) return setError("The date cannot be in the future.");
    setError("");
    add.mutate({ checkup_date: date, values: entered, notes: notes.trim() || null });
  };

  const filled = Object.values(values).filter((v) => v.trim() !== "").length;

  return (
    <div className="stack">
      <Card title="Add a check-up">
        <p className="hint">Enter only what is on your report. Typical ranges shown are for adults and differ between laboratories, so rely on the range printed on your own report.</p>
        <div className="grid2">
          <Field id="cdate" label="Date of the test"><input id="cdate" type="date" max={today()} value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field id="cnotes" label="Notes (optional)"><input id="cnotes" value={notes} maxLength={1000} onChange={(e) => setNotes(e.target.value)} /></Field>
        </div>
        {Object.entries(catalogue.data.categories).map(([cat, title]) => {
          const markers = catalogue.data.biomarkers.filter((b) => b.category === cat);
          const count = markers.filter((m) => (values[m.key] ?? "").trim() !== "").length;
          return (
            <div key={cat} className="accordion">
              <button type="button" aria-expanded={open === cat} onClick={() => setOpen(open === cat ? "" : cat)}>
                <span>{title}</span><span className="muted small">{count ? `${count} entered · ` : ""}{markers.length} measurements</span>
              </button>
              {open === cat && (
                <div className="grid3">
                  {markers.map((m) => (
                    <Field key={m.key} id={`lab-${m.key}`} label={`${m.label} (${m.unit})`} hint={m.low !== null && m.high !== null ? `Typical ${m.low} to ${m.high}` : undefined}>
                      <input id={`lab-${m.key}`} type="number" inputMode="decimal" step="any" value={values[m.key] ?? ""} onChange={(e) => setValues({ ...values, [m.key]: e.target.value })} />
                    </Field>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {error && <Notice tone="warn">{error}</Notice>}
        <div className="actions"><button className="btn primary" disabled={add.isPending} onClick={submit}>{add.isPending ? "Saving…" : `Save check-up${filled ? ` (${filled} value${filled === 1 ? "" : "s"})` : ""}`}</button></div>
      </Card>

      <Card title="Import many results from a CSV">
        <p className="muted">One row per test date, with a date column and any of the measurement columns. The whole file is rejected if any row has a problem, so nothing is half-imported.</p>
        <div className="row">
          <button className="btn ghost small" onClick={() => void download(`${base}/import/template`, "checkups-template.csv")}>Download template</button>
          <input aria-label="CSV file" type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button className="btn primary small" disabled={!file || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? "Importing…" : "Import"}</button>
        </div>
      </Card>

      <Card title="History" action={<button className="btn ghost small" onClick={() => void download(`${base}/export/checkups.csv`, "checkups.csv")}>Export CSV</button>}>
        {history.isLoading ? <Skeleton lines={4} /> : history.error || !history.data ? <ErrorState error={history.error} /> : history.data.length === 0 ? (
          <EmptyState title="No check-ups yet">Add your latest blood test above to start tracking trends and alerts.</EmptyState>
        ) : (
          <ul className="list">
            {history.data.map((c) => (
              <li key={c.id} className="col">
                <div className="row between">
                  <div><strong>{when(`${c.date}T12:00:00`).split(",")[0]}</strong> <span className={`prov ${c.source === "clinician" ? "prov-clinician" : "prov-reported"}`}>{c.source === "clinician" ? "Entered by clinician" : "Entered by patient"}</span></div>
                  <button className="btn ghost small" aria-label={`Delete check-up from ${c.date}`} onClick={() => remove.mutate(c.id)}>Delete</button>
                </div>
                <div className="chips">
                  {Object.entries(c.values).map(([k, v]) => (
                    <span key={k} className="value-chip"><b>{info.get(k)?.label ?? k}</b> {v} {info.get(k)?.unit}{" "}
                      {c.flags[k] && c.flags[k] !== "normal" && <StatusChip tone={STATUS_TONE[c.flags[k]]} label={STATUS_LABEL[c.flags[k]]} />}</span>
                  ))}
                </div>
                {c.notes && <p className="muted small">{c.notes}</p>}
              </li>
            ))}
          </ul>
        )}
        {viewer === "clinician" && <p className="muted small">Viewing this record is logged in the audit trail.</p>}
      </Card>
    </div>
  );
}
