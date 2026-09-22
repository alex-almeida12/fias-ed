import { useId, useRef } from "react";
import { Button } from "../design/components/Button";
import { formatBytes } from "./format";

export const AUDIO_ACCEPT = ".mp3,.wav,.m4a,.aac,.flac";

type Props = { file: File | null; onChange: (file: File | null) => void; label?: string };

export function AudioPicker({ file, onChange, label = "Selecionar áudio" }: Props) {
  const inputId = useId();
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div>
      <label htmlFor={inputId} className="visually-hidden">Arquivo de áudio</label>
      <input id={inputId} ref={ref} type="file" accept={AUDIO_ACCEPT} className="visually-hidden"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)} />
      <Button variant="secondary" onClick={() => ref.current?.click()}>{label}</Button>
      {file && <p className="meta">{file.name} · {formatBytes(file.size)}</p>}
    </div>
  );
}
