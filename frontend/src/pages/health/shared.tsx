import type { MarkerStatus } from "../../api/types";

export const STATUS_TONE: Record<MarkerStatus, "good" | "watch" | "action" | "unknown"> = {
  normal: "good", low: "watch", high: "watch", critical_low: "action", critical_high: "action", unknown: "unknown",
};

export const STATUS_LABEL: Record<MarkerStatus, string> = {
  normal: "Typical", low: "Low", high: "High", critical_low: "Critically low", critical_high: "Critically high", unknown: "No data",
};

export const SEVERITY_TONE = { info: "unknown", warning: "watch", critical: "action" } as const;

export interface HealthProps {
  base: string;
  viewer: "patient" | "clinician";
}

export const today = () => new Date().toISOString().slice(0, 10);
