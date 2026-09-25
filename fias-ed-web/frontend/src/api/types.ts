export type Role = "ADMIN_LOCAL" | "PROFESSOR";

export interface Me {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  must_change_password: boolean;
  acting_as: { id: string; display_name: string } | null;
}

export interface Escola { id: string; name: string; municipality: string | null; region: string | null }
export interface Turma { id: string; name: string; school_year: number | null; level: string | null; escola: Escola }
export interface Disciplina { id: string; name: string }

export interface AulaResumo {
  id: string;
  lesson_date: string;
  status: string;
  turma: { id: string; name: string };
  disciplina: { id: string; name: string };
  professor?: { id: string; display_name: string };
}

export interface AudioInfo {
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  duration_ms: number;
  channels: number;
  sample_rate: number;
}

export interface Aula extends AulaResumo {
  note: string | null;
  error_code: string | null;
  error_message: string | null;
  audio: AudioInfo | null;
  upload_pendente: { original_filename: string; size_bytes: number } | null;
  job_ativo: boolean;
  alterada_pelo_admin_em: string | null;
}

export interface VozAmostra { inicio_ms: number; fim_ms: number }

export interface Voz {
  rotulo: string;
  tempo_total_ms: number;
  n_segmentos: number;
  amostras: VozAmostra[];
}

export type Papel = "PROFESSOR" | "ALUNO";

export interface Segmento {
  id: string;
  start_ms: number;
  end_ms: number;
  texto: string;
  papel: Papel;
  version: number;
  revisado: boolean;
}

export interface TranscricaoBloco {
  bloco: number;
  blocos: number;
  segmentos: Segmento[];
}

export type FiasGrupo = "indireta" | "direta" | "estudante" | "silêncio";

export interface FaixaIntervalo {
  inicio_ms: number;
  fim_ms: number;
  grupo: FiasGrupo;
}

export interface Evidencia {
  segmento_id: string;
  inicio_ms: number;
  trecho: string;
}

export interface Observacao {
  texto: string;
  evidencias: Evidencia[];
}

export interface Indice {
  codigo: string;
  nome: string;
  valor: number | null;
  descricao: string;
}

export interface Padroes {
  faixa: FaixaIntervalo[];
  observacoes: Observacao[];
  matriz: number[][];
  indices: Indice[];
}

export type QtiAgreement = "agree" | "disagree" | "inconclusive" | "unpaired" | "no_qti";

export interface TriangulacaoQtiValor { octant: string; label: string; value: number | null }

export interface TriangulacaoPar {
  pair_id: string;
  fias: { kind: string; ref: string | number[]; value: number | null };
  qti_values: TriangulacaoQtiValor[];
  qti_available: boolean;
  reflection_question: string;
  source_reference: string;
  validation_status: string;
}

export interface InterpretacaoMTSS {
  rule_id: string;
  tier1_dimension: string;
  framing: string;
  interpretation: string;
  evidence: Record<string, unknown>;
  evidence_segment_categories: number[];
  source_reference: string;
  validation_status: string;
  rules_version: string;
  qti_agreement: QtiAgreement;
  qti_evidence: Record<string, unknown> | null;
  divergence_question: string | null;
  evidencias: Evidencia[];
}

export interface RecomendacaoMTSS {
  recommendation_id: string;
  rule_id: string;
  text: string;
  validation_status: string;
  source_reference: string;
  qti_agreement: QtiAgreement;
}

export interface Relatorio {
  aula: Aula;
  indices: Indice[];
  triangulacao: TriangulacaoPar[];
  interpretacoes: InterpretacaoMTSS[];
  recomendacoes: RecomendacaoMTSS[];
}

export interface Ciclo {
  id: string;
  turma: { id: string; name: string };
  disciplina: { id: string; name: string };
  n_aulas_previstas: number;
  iniciado_em: string;
  encerrado_em: string | null;
}

export interface TrajetoriaItem {
  aula_id: string;
  lesson_date: string;
  status: string;
  indices: Indice[];
}

export interface OctanteValor { octant: string; label: string; value: number }

export interface Coleta {
  id: string;
  coletado_em: string;
  origem: string;
  response_count: number;
  displayable: boolean;
  octantes: OctanteValor[];
}

export interface CicloRelatorio {
  ciclo: Ciclo;
  n_aulas_realizadas: number;
  trajetoria: TrajetoriaItem[];
  coletas: Coleta[];
}

export interface Conta {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}
