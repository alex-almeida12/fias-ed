import { useEffect, useId, useRef, type ReactNode } from "react";

type Props = { title: string; children: ReactNode; actions: ReactNode; onClose: () => void };

export function Dialog({ title, children, actions, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();

  // Revisão da Task 15: manter `onClose` numa ref, atualizada a cada render, e focar/registrar
  // o Esc uma única vez (montagem). Antes, um único efeito dependia de `[onClose]`: uma arrow
  // inline num formulário controlado ganha identidade nova a cada tecla digitada, o que refazia
  // o efeito e chamava `ref.current?.focus()` de novo — tirando o foco do campo no meio da
  // digitação (visto no diálogo de exclusão de conta, Contas.tsx).
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    ref.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="dialog-backdrop">
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} ref={ref}>
        <h2 id={titleId}>{title}</h2>
        <div>{children}</div>
        <div className="dialog__actions">{actions}</div>
      </div>
    </div>
  );
}
