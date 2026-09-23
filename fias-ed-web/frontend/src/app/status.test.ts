import { describe, expect, test } from "vitest";
import aulaSchema from "@shared/schemas/entities/aula.schema.json";
import { progressMessage, STATUS_TEXT, statusText, statusTone } from "./status";

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

// Task 15: cada estágio que anda sozinho tem a mensagem do §36 correspondente. Um
// "Preparando sua aula…" genérico em todos eles deixaria o professor sem saber se a
// aula andou ou travou numa aula de 90 min, que leva horas.
describe("mensagem de progresso (§36)", () => {
  test.each([
    ["PREPROCESSING", "Preparando sua aula…"],
    ["TRANSCRIBING", "Transformando áudio em texto…"],
    ["TRANSCRIBED", "Identificando os momentos de fala…"],
    ["DIARIZING", "Identificando os momentos de fala…"],
    ["READY_FOR_FIAS", "Analisando padrões da aula…"],
  ])("%s diz o que está acontecendo com a aula", (status, mensagem) => {
    expect(progressMessage(status, true)).toBe(mensagem);
  });

  test("nenhuma mensagem de progresso usa jargão técnico", () => {
    for (const status of statuses) {
      expect(progressMessage(status, true) ?? "").not.toMatch(/whisper|pyannote|bertimbau|diariz|ASR|modelo|infer/i);
    }
  });

  test("aula parada esperando o professor não finge estar processando", () => {
    for (const status of ["DRAFT", "AUDIO_IMPORTED", "AUDIO_VALIDATED", "READY_FOR_TRANSCRIPT_REVIEW",
                          "FIAS_COMPLETED", "ERROR"]) {
      expect(progressMessage(status, false)).toBeNull();
    }
  });

  test("um job em curso num estado sem mensagem própria ainda avisa que a aula anda", () => {
    expect(progressMessage("AUDIO_IMPORTED", true)).toBe("Preparando sua aula…");
  });
});
