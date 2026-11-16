import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import type { DiagnosisRow, DietRow, InteractionResult, MedicationRow } from "../../api/types";
import { useToast } from "../../components/Toast";
import { Card, EmptyState, ErrorState, Field, Notice, Skeleton, Spinner } from "../../components/ui";
import { HealthProps } from "./shared";

const SEVERITY_CLASS = { contraindicated: "danger", major: "danger", moderate: "warn" } as const;
const sourceBadge = (s: string) => <span className={`prov ${s === "clinician" ? "prov-clinician" : "prov-reported"}`}>{s === "clinician" ? "Clinician" : "Patient"}</span>;

function InteractionPanel({ result }: { result: InteractionResult }) {
  return (
    <div className="stack-tight">
      {result.interactions.map((i) => (
        <Notice key={i.medicines.join("+")} tone={SEVERITY_CLASS[i.severity]} title={`${i.medicines.join(" + ")}: ${i.severity === "contraindicated" ? "do not combine" : `${i.severity} interaction`}`}>
          {i.effect} <strong>{i.advice}</strong>
        </Notice>
      ))}
      {result.interactions.length === 0 && <Notice tone="good">No known interactions found in our list.</Notice>}
      {result.not_covered.length > 0 && <p className="muted small">No interaction rules for: {result.not_covered.join(", ")}.</p>}
      <p className="muted small">{result.note}</p>
    </div>
  );
}

export function MedicationsTab({ base }: HealthProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState({ name: "", dose: "", frequency: "", reason: "" });
  const [error, setError] = useState("");
  const [names, setNames] = useState("");
  const [checked, setChecked] = useState<InteractionResult | null>(null);
  const list = useQuery({ queryKey: ["medications", base], queryFn: () => api<{ medications: MedicationRow[]; interactions: InteractionResult }>(`${base}/medications`) });
  const refresh = () => { for (const k of ["medications", "summary", "dashboard"]) void queryClient.invalidateQueries({ queryKey: [k] }); };
  const add = useMutation({
    mutationFn: () => api(`${base}/medications`, { method: "POST", body: { name: f.name, dose: f.dose || null, frequency: f.frequency || null, reason: f.reason || null } }),
    onSuccess: () => { setF({ name: "", dose: "", frequency: "", reason: "" }); setError(""); toast.success("Medication added."); refresh(); },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not add."),
  });
  const toggle = useMutation({ mutationFn: (m: MedicationRow) => api(`${base}/medications/${m.id}`, { method: "PATCH", body: { is_active: !m.is_active } }), onSuccess: refresh });
  const remove = useMutation({
    mutationFn: (id: number) => api(`${base}/medications/${id}`, { method: "DELETE" }),
    onSuccess: () => { toast.success("Medication removed."); refresh(); },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not remove."),
  });
  const check = useMutation({
    mutationFn: () => api<InteractionResult>(`${base}/interactions/check`, { method: "POST", body: { medicines: names.split(",").map((n) => n.trim()).filter(Boolean) } }),
    onSuccess: setChecked,
    onError: (e) => toast.error(e instanceof Error ? e.message : "Enter at least two medicines separated by commas."),
  });
  if (list.isLoading) return <Skeleton lines={5} height={22} />;
  if (list.error || !list.data) return <ErrorState error={list.error} retry={() => void list.refetch()} />;
  const active = list.data.medications.filter((m) => m.is_active);
  return (
    <div className="stack">
      {list.data.interactions.interactions.length > 0 && (
        <Card title="Interactions between current medicines"><InteractionPanel result={list.data.interactions} /></Card>
      )}
      <Card title="Add a medication">
        <div className="grid2">
          <Field id="mname" label="Name (brand or generic)"><input id="mname" value={f.name} maxLength={120} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field id="mdose" label="Dose"><input id="mdose" value={f.dose} maxLength={60} placeholder="for example 75 mg" onChange={(e) => setF({ ...f, dose: e.target.value })} /></Field>
          <Field id="mfreq" label="How often"><input id="mfreq" value={f.frequency} maxLength={60} placeholder="for example once daily" onChange={(e) => setF({ ...f, frequency: e.target.value })} /></Field>
          <Field id="mreason" label="What it is for"><input id="mreason" value={f.reason} maxLength={120} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field>
        </div>
        {error && <Notice tone="warn">{error}</Notice>}
        <div className="actions"><button className="btn primary" disabled={f.name.trim().length < 2 || add.isPending} onClick={() => { setError(""); add.mutate(); }}>Add medication</button></div>
      </Card>
      <Card title={`Medications (${active.length} active)`}>
        {list.data.medications.length === 0 ? <EmptyState title="No medications recorded" /> : (
          <ul className="list">
            {list.data.medications.map((m) => (
              <li key={m.id} className={m.is_active ? "" : "faded"}>
                <div><strong>{m.name}</strong> {sourceBadge(m.source)}<span className="muted small">{[m.dose, m.frequency, m.reason].filter(Boolean).join(" · ") || "No details"}{m.is_active ? "" : ` · stopped ${m.end_date ?? ""}`}</span></div>
                <div className="row"><button className="btn ghost small" onClick={() => toggle.mutate(m)}>{m.is_active ? "Mark as stopped" : "Restart"}</button>
                  <button className="btn ghost small" aria-label={`Remove ${m.name}`} onClick={() => remove.mutate(m.id)}>Remove</button></div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Check a combination">
        <p className="muted">Planning to take something new? Enter medicines separated by commas, for example <em>warfarin, ibuprofen</em>.</p>
        <div className="inline-form"><Field id="combo" label="Medicines"><input id="combo" value={names} onChange={(e) => setNames(e.target.value)} /></Field>
          <button className="btn primary" disabled={check.isPending} onClick={() => check.mutate()}>Check</button></div>
        {check.isPending && <Spinner label="Checking" />}
        {checked && <InteractionPanel result={checked} />}
      </Card>
    </div>
  );
}

export function DiagnosesTab({ base, viewer }: HealthProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState({ icd10: "", description: "", severity: "", status: "active" });
  const [error, setError] = useState("");
  const list = useQuery({ queryKey: ["diagnoses", base], queryFn: () => api<DiagnosisRow[]>(`${base}/diagnoses`) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["diagnoses"] });
  const add = useMutation({
    mutationFn: () => api(`${base}/diagnoses`, { method: "POST", body: { icd10: f.icd10.trim(), description: f.description, severity: f.severity || null, status: f.status } }),
    onSuccess: () => { setF({ icd10: "", description: "", severity: "", status: "active" }); setError(""); toast.success("Diagnosis added."); refresh(); },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not add."),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`${base}/diagnoses/${id}`, { method: "DELETE" }),
    onSuccess: () => { toast.success("Removed."); refresh(); },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not remove."),
  });
  if (list.isLoading) return <Skeleton lines={4} height={22} />;
  if (list.error || !list.data) return <ErrorState error={list.error} retry={() => void list.refetch()} />;
  return (
    <div className="stack">
      <Card title="Add a diagnosis">
        <p className="muted">{viewer === "patient" ? "Diagnoses you add are labelled as patient-reported. Those entered by a clinician are labelled separately." : "Entries you add are labelled as clinician-entered."}</p>
        <div className="grid2">
          <Field id="icd" label="ICD-10 code" hint="For example I10 or E11.9"><input id="icd" value={f.icd10} maxLength={10} onChange={(e) => setF({ ...f, icd10: e.target.value })} /></Field>
          <Field id="dd" label="Description"><input id="dd" value={f.description} maxLength={200} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
          <Field id="ds" label="Severity"><select id="ds" value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}><option value="">Not stated</option><option value="mild">Mild</option><option value="moderate">Moderate</option><option value="severe">Severe</option></select></Field>
          <Field id="dstat" label="Status"><select id="dstat" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="active">Active</option><option value="resolved">Resolved</option></select></Field>
        </div>
        {error && <Notice tone="warn">{error}</Notice>}
        <div className="actions"><button className="btn primary" disabled={!f.icd10.trim() || f.description.trim().length < 3 || add.isPending} onClick={() => { setError(""); add.mutate(); }}>Add diagnosis</button></div>
      </Card>
      <Card title="Diagnoses">
        {list.data.length === 0 ? <EmptyState title="No diagnoses recorded" /> : (
          <ul className="list">
            {list.data.map((d) => (
              <li key={d.id}><div><strong>{d.icd10}</strong> {d.description} {sourceBadge(d.source)}<span className="muted small">{[d.severity, d.status].filter(Boolean).join(" · ")}</span></div>
                <button className="btn ghost small" aria-label={`Remove ${d.icd10}`} onClick={() => remove.mutate(d.id)}>Remove</button></li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export function DietTab({ base }: HealthProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState({ name: "", diet_type: "", calories: "", protein: "", restrictions: "", notes: "" });
  const [error, setError] = useState("");
  const list = useQuery({ queryKey: ["diets", base], queryFn: () => api<DietRow[]>(`${base}/diet-plans`) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["diets"] });
  const n = (v: string) => (v.trim() === "" ? null : Number(v));
  const add = useMutation({
    mutationFn: () => api(`${base}/diet-plans`, { method: "POST", body: { name: f.name, diet_type: f.diet_type || null, calories: n(f.calories), protein_g: n(f.protein),
      restrictions: f.restrictions.split(",").map((x) => x.trim()).filter(Boolean), notes: f.notes || null } }),
    onSuccess: () => { setF({ name: "", diet_type: "", calories: "", protein: "", restrictions: "", notes: "" }); setError(""); toast.success("Diet plan added."); refresh(); },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not add."),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`${base}/diet-plans/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not remove."),
  });
  if (list.isLoading) return <Skeleton lines={4} height={22} />;
  if (list.error || !list.data) return <ErrorState error={list.error} retry={() => void list.refetch()} />;
  return (
    <div className="stack">
      <Card title="Add a diet plan">
        <div className="grid2">
          <Field id="dpn" label="Plan name"><input id="dpn" value={f.name} maxLength={120} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field id="dpt" label="Type"><input id="dpt" value={f.diet_type} maxLength={40} placeholder="for example Mediterranean" onChange={(e) => setF({ ...f, diet_type: e.target.value })} /></Field>
          <Field id="dpc" label="Calories per day"><input id="dpc" type="number" value={f.calories} onChange={(e) => setF({ ...f, calories: e.target.value })} /></Field>
          <Field id="dpp" label="Protein (g per day)"><input id="dpp" type="number" value={f.protein} onChange={(e) => setF({ ...f, protein: e.target.value })} /></Field>
        </div>
        <Field id="dpr" label="Restrictions, separated by commas"><input id="dpr" value={f.restrictions} placeholder="low salt, no fried food" onChange={(e) => setF({ ...f, restrictions: e.target.value })} /></Field>
        <Field id="dpnotes" label="Notes"><input id="dpnotes" value={f.notes} maxLength={500} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
        {error && <Notice tone="warn">{error}</Notice>}
        <div className="actions"><button className="btn primary" disabled={f.name.trim().length < 2 || add.isPending} onClick={() => { setError(""); add.mutate(); }}>Add plan</button></div>
      </Card>
      <Card title="Diet plans">
        {list.data.length === 0 ? <EmptyState title="No diet plans yet" /> : (
          <ul className="list">
            {list.data.map((d) => (
              <li key={d.id}><div><strong>{d.name}</strong> {sourceBadge(d.source)}
                <span className="muted small">{[d.diet_type, d.calories ? `${d.calories} kcal` : null, d.protein_g ? `${d.protein_g} g protein` : null].filter(Boolean).join(" · ")}</span>
                {d.restrictions.length > 0 && <span className="muted small">Avoid or limit: {d.restrictions.join(", ")}</span>}
                {d.notes && <span className="muted small">{d.notes}</span>}</div>
                <button className="btn ghost small" aria-label={`Remove ${d.name}`} onClick={() => remove.mutate(d.id)}>Remove</button></li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
