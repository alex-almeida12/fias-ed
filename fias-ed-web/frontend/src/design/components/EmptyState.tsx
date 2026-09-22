import type { ReactNode } from "react";

type Props = { title: string; children: ReactNode; action?: ReactNode };

export function EmptyState({ title, children, action }: Props) {
  return (
    <section className="empty">
      <h2 className="empty__title">{title}</h2>
      <p>{children}</p>
      {action}
    </section>
  );
}
