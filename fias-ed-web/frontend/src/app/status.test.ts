import { describe, expect, test } from "vitest";
import aulaSchema from "@shared/schemas/entities/aula.schema.json";
import { STATUS_TEXT, statusText, statusTone } from "./status";

type Part = { properties?: { status?: { enum: string[] } } };
const statuses = (aulaSchema as { allOf: Part[] }).allOf.find((p) => p.properties?.status)!.properties!.status!.enum;

describe("status em linguagem humana", () => {
  test.each(statuses)("%s tem texto", (s) => {
    expect(STATUS_TEXT[s]).toBeTruthy();
  });

  test("nenhum texto usa vocabulário de julgamento", () => {
    for (const text of Object.values(STATUS_TEXT)) expect(text).not.toMatch(/avalia|nota|desempenho|ruim/i);
  });

  test("tons", () => {
    expect(statusTone("ERROR")).toBe("attention");
    expect(statusTone("READY_FOR_SPEAKER_REVIEW")).toBe("attention");
    expect(statusTone("AUDIO_VALIDATED")).toBe("done");
    expect(statusTone("TRANSCRIBING")).toBe("progress");
    expect(statusText("DRAFT")).toBe("Aguardando o áudio da aula");
  });
});
