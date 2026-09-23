/**
 * Workflow Economics — Jev-style decision primitives.
 *
 * Shared TypeScript types for every decision record in this workspace.
 * Each decision record also embeds its own question set; this file is the
 * vocabulary those sets build on. Mirrors `docs/decisions/workflow-economics/README.md`.
 */

/** How a decision is resolved. */
export type DecisionResolution =
  | { kind: "decision"; optionId: string }
  | { kind: "bounded-experiment"; optionId: string; duration: string; stopRule: string }
  | { kind: "defer"; revisit: string }
  | { kind: "escalate"; reason: string };

/** Status lifecycle of a record. */
export type DecisionStatus = "proposed" | "accepted" | "rejected" | "deferred" | "superseded";

/** Confidence for a single score or estimate. */
export type Confidence = "high" | "medium" | "low";

/** 0–5 rubric axis (see README rubric table). */
export type Criterion =
  | "workflow_leverage"
  | "cost_impact"
  | "quality_preservation"
  | "local_first"          // privacy / local-first
  | "reversibility"
  | "complexity"           // 5 = simplest to build & keep
  | "time_to_value"
  | "observability"
  | "extensibility";

/** A crystalline unit of judgment: one option scored on one criterion. */
export type Score = {
  criterion: Criterion;
  optionId: string;
  value: 0 | 1 | 2 | 3 | 4 | 5;
  /** evidence (file path / measurement) OR explicitly "assumption" */
  basis: "evidence" | "assumption";
  source?: string;         // repo/log path, only meaningful when basis === "evidence"
  confidence: Confidence;
  note?: string;
};

/** A single bounded decision question. */
export type DecisionQuestion =
  | { primitive: "CHOICE"; stem: string; optionIds: string[] }
  | { primitive: "SCORE"; stem: string; options: Record<string, Criterion[]> }
  | {
      primitive: "NOUL";
      /** a narrow proposition to bet true/false (single claim) */
      proposition: string;
      prevalence?: number;  // optional prior
    }
  | { primitive: "HARD_CONSTRAINT"; rule: string; pass?: boolean }
  | { primitive: "ESCALATE"; stem: string; why: string };

export type DecisionPrimitive = DecisionQuestion["primitive"];

/** A full decision record (mirrors the required ADR sections). */
export type DecisionRecord<QMeta extends DecisionQuestion = DecisionQuestion> = {
  id: string;                       // NNNN-short-name
  status: DecisionStatus;
  date: string;                     // ISO date
  owner: string;
  statement: string;                // one bounded question
  deadlineOrRevisit: string;
  context: string;
  constraints: string[];            // non-negotiable
  options: Array<{ id: string; name: string; description: string }>;
  as: { noop: string; experiment: string }; // "do nothing" and "bounded experiment" options render here
  criterionWeights: Partial<Record<Criterion, number>>; // sum ≈ 1.0
  scores: Score[];
  unknowns: string[];
  questions: QMeta;
  recommendation: DecisionResolution;
  humanDecisionRequired: string;    // what needs your explicit value judgment
  implementation: string[];
  validation: string[];
  revisit: string[];
};

// ---- JSON Schema (equivalent to the TS types) ----
export const decisionRecordJsonSchema = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  title: "JevDecisionRecord",
  type: "object",
  required: [
    "id", "status", "date", "statement", "context", "constraints",
    "options", "scores", "recommendation", "humanDecisionRequired",
  ],
  properties: {
    status: { enum: ["proposed", "accepted", "rejected", "deferred", "superseded"] },
    scores: {
      type: "array",
      items: {
        type: "object",
        required: ["criterion", "optionId", "score", "basis", "confidence"],
        properties: {
          score: { type: "integer", minimum: 0, maximum: 5 },
          basis: { enum: ["evidence", "assumption"] },
          confidence: { enum: ["high", "medium", "low"] },
        },
      },
    },
    primitives: { type: "array" },
  },
  additionalProperties: true,
} as const;

export type { DecisionRecord as DecisionRecordT };