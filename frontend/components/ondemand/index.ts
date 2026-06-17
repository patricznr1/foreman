// ============================================================
//  FOREMAN Frontend — components/ondemand/index.ts
//  Zweck: Sammel-Export des GETEILTEN On-Demand-Musters (Studie §3.2) — Trigger →
//         benannter Verarbeitungszustand → Ergebnis mit Herkunft. Wiederverwendbar
//         für E (Ausfallvorhersage) und die späteren On-Demand-Sektionen D/F/G/H.
// ============================================================
export { TriggerButton, type TriggerButtonProps } from "./trigger-button";
export {
  NamedProcessingState,
  type NamedProcessingStateProps,
} from "./named-processing-state";
export {
  ResultWithProvenance,
  type ResultWithProvenanceProps,
} from "./result-with-provenance";
