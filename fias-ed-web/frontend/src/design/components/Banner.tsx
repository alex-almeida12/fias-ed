import type { ReactNode } from "react";

type Props = { kind?: "info" | "error" | "warning" | "success"; children: ReactNode };

export function Banner({ kind = "info", children }: Props) {
  return (
    <div className={`banner banner--${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}
