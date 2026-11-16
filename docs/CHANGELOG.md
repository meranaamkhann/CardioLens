# Changelog

## 1.2

Longitudinal health record, shared by patients and clinicians: 46 biomarkers in 7 categories with sex-specific typical ranges; lab check-ups with CSV import (atomic, validated) and export; trend analysis using a robust median slope; value alerts (critical, warning, note) and trend alerts; medications with a curated drug-interaction checker and brand-name aliases; ICD-10 diagnoses; diet plans; overdue check-up reminders; clinic-wide alert and overdue views; provenance labels on every entry; lab values feed symptom assessments; health data is included in the data export and removed with the account. New migration 0002.

## 1.1

Model: bootstrap score ranges, random-forest second opinion with agreement statistics, finer regularisation grid.
Patients: step-by-step symptom assessment with progress, review step and session-only draft saving; blood pressure, cholesterol and glucose status labels; blood pressure trend and urgency timeline on the overview; larger-text mode; toasts; skeleton loaders; a log of who viewed their record; full data download; account deletion with password confirmation.
Clinicians: urgency filters, patient search and an emergency banner on the review queue.
Researchers: compare two experiments side by side.
Accessibility: route changes update the page title and move focus without interrupting typing; larger text persists across visits.
Fixed: login redirect race after sign-in (1.0); focus stealing during typing introduced and fixed during 1.1 development.
