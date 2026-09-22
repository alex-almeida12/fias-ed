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

export interface Conta {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}
