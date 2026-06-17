// ============================================================
//  FOREMAN Frontend — lib/capture/submit.test.ts
//  Zweck: Sichert Payload-Bildung, Status-Klassifikation und den Sendepfad gegen
//         den realen POST-Vertrag (Happy / Validation / Auth / transienter Fehler).
// ============================================================
import { describe, expect, it, vi } from "vitest";
import type { WorkerNoteRead } from "@/lib/api/contracts";
import { buildNotePayload, classifyStatus, isSubmittable, submitNote } from "./submit";
import { makeDraft } from "./testing/fixtures";

describe("buildNotePayload", () => {
  it("trimmt den Text und lässt leere optionale Felder weg (Backend setzt None)", () => {
    const payload = buildNotePayload(makeDraft({ text: "  Lager heiß  " }), null);
    expect(payload).toEqual({ text: "Lager heiß" });
    expect("machine_id" in payload).toBe(false);
    expect("shift" in payload).toBe(false);
    expect("classification" in payload).toBe(false);
    expect("author" in payload).toBe(false);
  });

  it("übernimmt Maschine, Schicht, Kategorie und Autor wenn gesetzt", () => {
    const payload = buildNotePayload(
      makeDraft({ text: "Späne bläulich", machineId: 12, shift: "Frueh", classification: "kritisch" }),
      "42",
    );
    expect(payload).toEqual({
      text: "Späne bläulich",
      machine_id: 12,
      shift: "Frueh",
      classification: "kritisch",
      author: "42",
    });
  });

  it("sendet classification MIT (Werker-Kategorie) — Anschlusspunkt, Backend verwirft heute still", () => {
    const payload = buildNotePayload(makeDraft({ classification: "auffaellig" }), null);
    expect(payload.classification).toBe("auffaellig");
  });
});

describe("isSubmittable", () => {
  it("verlangt einen nicht-leeren Text (Pflichtfeld)", () => {
    expect(isSubmittable(makeDraft({ text: "etwas" }))).toBe(true);
    expect(isSubmittable(makeDraft({ text: "" }))).toBe(false);
    expect(isSubmittable(makeDraft({ text: "   " }))).toBe(false);
  });
});

describe("classifyStatus", () => {
  it("mappt HTTP-Status auf Outcome-Klassen (hart vs. transient)", () => {
    expect(classifyStatus(201)).toBe("ok");
    expect(classifyStatus(200)).toBe("ok");
    expect(classifyStatus(422)).toBe("validation");
    expect(classifyStatus(401)).toBe("unauthorized");
    expect(classifyStatus(403)).toBe("forbidden");
    expect(classifyStatus(500)).toBe("error");
    expect(classifyStatus(0)).toBe("error");
  });
});

describe("submitNote", () => {
  const note: WorkerNoteRead = {
    id: 7,
    machine_id: 12,
    shift: "Frueh",
    text: "[PERSON] meldet Lager heiß", // bereits serverseitig NER-maskiert
    classification: null,
    author: "v1:ab12cd34",
    created_at: "2026-06-17T15:00:00+00:00",
  };

  it("Happy-Path: 201 liefert die erfasste (NER-maskierte) Notiz zurück", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      status: 201,
      json: async () => note,
    });
    const result = await submitNote({ text: "Lager heiß" }, fetchImpl as unknown as typeof fetch);
    expect(result).toEqual({ ok: true, note });
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v1/worker_notes",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
  });

  it("Validation-Fail: 422 ist ein harter Fehler (nicht erneut versuchen)", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ status: 422, json: async () => ({}) });
    const result = await submitNote({ text: "" }, fetchImpl as unknown as typeof fetch);
    expect(result).toEqual({ ok: false, reason: "validation", status: 422 });
  });

  it("Auth-Fail: 401 ist hart (Sitzung abgelaufen)", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ status: 401, json: async () => ({}) });
    const result = await submitNote({ text: "x" }, fetchImpl as unknown as typeof fetch);
    expect(result).toEqual({ ok: false, reason: "unauthorized", status: 401 });
  });

  it("Edge-Case: Netz-/Server-Fehler ist transient (Queue darf erneut senden)", async () => {
    const reject = vi.fn().mockRejectedValue(new Error("offline"));
    expect(await submitNote({ text: "x" }, reject as unknown as typeof fetch)).toEqual({
      ok: false,
      reason: "error",
    });
    const five = vi.fn().mockResolvedValue({ status: 503, json: async () => ({}) });
    expect(await submitNote({ text: "x" }, five as unknown as typeof fetch)).toEqual({
      ok: false,
      reason: "error",
      status: 503,
    });
  });
});
