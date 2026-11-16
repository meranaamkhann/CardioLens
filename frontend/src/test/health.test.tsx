import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import Dashboard from "../pages/patient/Dashboard";
import ClinicHealth from "../pages/clinic/ClinicHealth";
import HealthRecord from "../pages/health/HealthRecord";
import clinicAlerts from "./fixtures/clinic_alerts.json";
import clinicOverdue from "./fixtures/clinic_overdue.json";
import dashboard from "./fixtures/dashboard.json";
import catalogue from "./fixtures/h_catalogue.json";
import alerts from "./fixtures/h_alerts.json";
import checkups from "./fixtures/h_checkups.json";
import diagnoses from "./fixtures/h_diagnoses.json";
import diets from "./fixtures/h_diets.json";
import medications from "./fixtures/h_medications.json";
import summary from "./fixtures/h_summary.json";
import trends from "./fixtures/h_trends.json";
import { mockApi, renderApp } from "./helpers";

const BASE = "/api/me/health";

function api(extra?: (url: string, init?: RequestInit) => { status?: number; body?: unknown } | undefined) {
  return mockApi((url, init) => {
    const found = extra?.(url, init);
    if (found) return found;
    if (url.endsWith(`${BASE}/biomarkers`)) return { body: catalogue };
    if (url.endsWith(`${BASE}/checkups`) && init?.method !== "POST") return { body: checkups };
    if (url.endsWith(`${BASE}/trends`)) return { body: trends };
    if (url.includes(`${BASE}/alerts`)) return { body: alerts.filter((a) => !a.resolved) };
    if (url.endsWith(`${BASE}/medications`)) return { body: medications };
    if (url.endsWith(`${BASE}/diagnoses`)) return { body: diagnoses };
    if (url.endsWith(`${BASE}/diet-plans`)) return { body: diets };
    if (url.endsWith(`${BASE}/summary`)) return { body: summary };
    return undefined;
  });
}

const open = () => renderApp(<HealthRecord base="/me/health" viewer="patient" />);

describe("health record", () => {
  it("warns about serious medicine interactions and shows the history with provenance", async () => {
    api();
    open();
    expect(await screen.findByText("Serious medicine interaction")).toBeInTheDocument();
    expect((await screen.findAllByText("Entered by patient")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Haemoglobin/).length).toBeGreaterThan(0);
  });

  it("blocks impossible lab values before sending anything", async () => {
    const spy = api();
    open();
    await userEvent.click(await screen.findByRole("button", { name: /Blood count/ }));
    await userEvent.type(await screen.findByLabelText(/Haemoglobin \(g\/dL\)/), "99");
    await userEvent.click(screen.getByRole("button", { name: /Save check-up/ }));
    expect(await screen.findByText(/Haemoglobin must be between 3 and 25 g\/dL/)).toBeInTheDocument();
    expect(spy.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("requires at least one value, then saves a valid check-up", async () => {
    const spy = api((url, init) => (url.endsWith(`${BASE}/checkups`) && init?.method === "POST" ? { status: 201, body: checkups[0] } : undefined));
    open();
    await userEvent.click(await screen.findByRole("button", { name: /Save check-up/ }));
    expect(await screen.findByText("Enter at least one measurement.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Blood count/ }));
    await userEvent.type(await screen.findByLabelText(/Haemoglobin \(g\/dL\)/), "13.8");
    await userEvent.click(screen.getByRole("button", { name: /Save check-up \(1 value\)/ }));
    await waitFor(() => expect(spy.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const post = spy.mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(JSON.parse(String(post[1]?.body)).values).toEqual({ hemoglobin: 13.8 });
  });

  it("shows trend alerts, status chips and a chart for the selected marker", async () => {
    api();
    open();
    await userEvent.click(await screen.findByRole("tab", { name: "Trends" }));
    expect(await screen.findByText("Trends worth discussing with a doctor")).toBeInTheDocument();
    expect(screen.getAllByText(/not a diagnosis/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/results?/).length).toBeGreaterThan(0);
    await userEvent.selectOptions(screen.getByLabelText("Measurement"), "ldl");
    expect(screen.getByRole("img", { name: /LDL cholesterol over time/ })).toBeInTheDocument();
  });

  it("lets the user mark an alert as seen", async () => {
    const spy = api((url, init) => (url.includes("/acknowledge") && init?.method === "POST" ? { body: { ...alerts[0], acknowledged: true } } : undefined));
    open();
    await userEvent.click(await screen.findByRole("tab", { name: /Alerts/ }));
    const buttons = await screen.findAllByRole("button", { name: "Mark as seen" });
    await userEvent.click(buttons[0]);
    await waitFor(() => expect(spy.mock.calls.some(([u, i]) => String(u).includes("/acknowledge") && i?.method === "POST")).toBe(true));
  });

  it("explains each interaction and what to do about it", async () => {
    api();
    open();
    await userEvent.click(await screen.findByRole("tab", { name: "Medications" }));
    const panel = (await screen.findByText("Interactions between current medicines")).closest("section") as HTMLElement;
    expect(within(panel).getByText(/Higher risk of serious bleeding/)).toBeInTheDocument();
    expect(within(panel).getByText(/not exhaustive/)).toBeInTheDocument();
  });

  it("checks a combination typed by the user", async () => {
    const spy = api((url, init) => (url.endsWith(`${BASE}/interactions/check`) && init?.method === "POST"
      ? { body: { interactions: [{ medicines: ["sildenafil", "nitroglycerin"], severity: "contraindicated", effect: "Can cause a sudden, dangerous drop in blood pressure.", advice: "Never take together." }], not_covered: [], note: "Not exhaustive." } }
      : undefined));
    open();
    await userEvent.click(await screen.findByRole("tab", { name: "Medications" }));
    await userEvent.type(await screen.findByLabelText("Medicines"), "sildenafil, nitroglycerin");
    await userEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(await screen.findByText(/do not combine/)).toBeInTheDocument();
    const post = spy.mock.calls.find(([u]) => String(u).endsWith("/interactions/check"))!;
    expect(JSON.parse(String(post[1]?.body)).medicines).toEqual(["sildenafil", "nitroglycerin"]);
  });

  it("rejects a malformed ICD-10 code with the server message", async () => {
    api((url, init) => (url.endsWith(`${BASE}/diagnoses`) && init?.method === "POST" ? { status: 422, body: { detail: "String should match pattern" } } : undefined));
    open();
    await userEvent.click(await screen.findByRole("tab", { name: "Diagnoses" }));
    await userEvent.type(await screen.findByLabelText("ICD-10 code"), "12");
    await userEvent.type(screen.getByLabelText("Description"), "Not a real code");
    await userEvent.click(screen.getByRole("button", { name: "Add diagnosis" }));
    expect(await screen.findByText("String should match pattern")).toBeInTheDocument();
  });

  it("lists diet plans with their restrictions", async () => {
    api();
    open();
    await userEvent.click(await screen.findByRole("tab", { name: "Diet" }));
    expect(await screen.findByText("Heart-friendly")).toBeInTheDocument();
    expect(screen.getByText(/Avoid or limit: low salt/)).toBeInTheDocument();
  });

  it("shows an empty state for a patient with no results", async () => {
    mockApi((url) => {
      if (url.endsWith(`${BASE}/biomarkers`)) return { body: catalogue };
      if (url.endsWith(`${BASE}/checkups`)) return { body: [] };
      if (url.endsWith(`${BASE}/summary`)) return { body: { ...summary, open_alerts: 0, critical_alerts: 0, serious_interactions: 0, overdue: { ...summary.overdue, overdue: false } } };
      return undefined;
    });
    open();
    expect(await screen.findByText("No check-ups yet")).toBeInTheDocument();
  });

  it("surfaces health warnings on the patient overview", async () => {
    mockApi((url) => {
      if (url.endsWith("/me/dashboard")) return { body: { ...dashboard, health: { open_alerts: 2, critical_alerts: 1, interaction_count: 1, serious_interactions: 1, overdue: { status: "overdue", overdue: true, days_since: 120, last_checkup: "2026-01-01", message: "Your last recorded check-up was 120 days ago." } } } };
      return undefined;
    });
    renderApp(<Dashboard />);
    expect(await screen.findByText("1 critical lab result")).toBeInTheDocument();
    expect(screen.getByText("Serious medicine interaction")).toBeInTheDocument();
    expect(screen.getByText(/120 days ago/)).toBeInTheDocument();
  });

  it("gives clinicians clinic-wide alerts and overdue patients", async () => {
    mockApi((url) => {
      if (url.endsWith("/clinic/health/alerts")) return { body: clinicAlerts.length ? clinicAlerts : [{ id: 1, patient_id: 5, patient_name: "Pat Ient", severity: "critical", kind: "value", biomarker: "hemoglobin", label: "Haemoglobin", message: "Haemoglobin 6.5 g/dL is critically low.", created_at: "2026-11-01T10:00:00Z", resolved: false, acknowledged: false }] };
      if (url.endsWith("/clinic/health/overdue")) return { body: clinicOverdue.length ? clinicOverdue : [{ patient_id: 6, patient_name: "Late Patient", status: "overdue", overdue: true, days_since: 150, last_checkup: "2026-06-01", message: "x" }] };
      return undefined;
    });
    renderApp(<Routes><Route path="/" element={<ClinicHealth />} /></Routes>);
    expect(await screen.findByText("Open lab alerts")).toBeInTheDocument();
    expect(await screen.findByText("Overdue check-ups")).toBeInTheDocument();
    expect(await screen.findAllByRole("button", { name: "Acknowledge" })).not.toHaveLength(0);
  });
});
