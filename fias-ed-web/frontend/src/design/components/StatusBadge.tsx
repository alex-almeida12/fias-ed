import { statusText, statusTone } from "../../app/status";

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge--${statusTone(status)}`}>{statusText(status)}</span>;
}
