import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "tertiary" };

export function Button({ variant = "primary", className = "", type = "button", ...props }: Props) {
  return <button type={type} className={`btn btn--${variant} ${className}`.trim()} {...props} />;
}
