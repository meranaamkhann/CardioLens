import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import type { HealthSummary } from "../../api/types";
import { Notice, Tabs } from "../../components/ui";
import AlertsTab from "./AlertsTab";
import { DiagnosesTab, DietTab, MedicationsTab } from "./CareTab";
import LabsTab from "./LabsTab";
import { HealthProps } from "./shared";
import TrendsTab from "./TrendsTab";

type Tab = "labs" | "trends" | "alerts" | "medications" | "diagnoses" | "diet";

export default function HealthRecord(props: HealthProps) {
  const [tab, setTab] = useState<Tab>("labs");
  const summary = useQuery({ queryKey: ["summary", props.base], queryFn: () => api<HealthSummary>(`${props.base}/summary`) });
  const s = summary.data;
  return (
    <div className="stack">
      {s && s.critical_alerts > 0 && (
        <Notice tone="danger" title={`${s.critical_alerts} critical result${s.critical_alerts === 1 ? "" : "s"}`}>
          {props.viewer === "patient" ? "Contact your doctor promptly, and check the value was entered correctly." : "Review the Alerts tab for this patient."}
        </Notice>
      )}
      {s && s.serious_interactions > 0 && (
        <Notice tone="warn" title="Serious medicine interaction">Review the Medications tab and speak to a pharmacist or doctor before taking these together.</Notice>
      )}
      {s && s.overdue.overdue && <Notice tone="info" title="Check-up reminder">{s.overdue.message}</Notice>}
      <Tabs value={tab} onChange={setTab} tabs={[
        { id: "labs", label: "Lab results" }, { id: "trends", label: "Trends" },
        { id: "alerts", label: `Alerts${s && s.open_alerts ? ` (${s.open_alerts})` : ""}` },
        { id: "medications", label: "Medications" }, { id: "diagnoses", label: "Diagnoses" }, { id: "diet", label: "Diet" }]} />
      {tab === "labs" && <LabsTab {...props} />}
      {tab === "trends" && <TrendsTab {...props} />}
      {tab === "alerts" && <AlertsTab {...props} />}
      {tab === "medications" && <MedicationsTab {...props} />}
      {tab === "diagnoses" && <DiagnosesTab {...props} />}
      {tab === "diet" && <DietTab {...props} />}
    </div>
  );
}
