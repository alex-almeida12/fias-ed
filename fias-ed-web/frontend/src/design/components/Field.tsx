import { useId, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

type Common = { label: string; error?: string };

function useFieldIds(id?: string) {
  const auto = useId();
  const fieldId = id ?? auto;
  return { fieldId, errorId: `${fieldId}-erro` };
}

export function TextField({ label, error, id, ...input }: InputHTMLAttributes<HTMLInputElement> & Common) {
  const { fieldId, errorId } = useFieldIds(id);
  return (
    <div className="field">
      <label className="field__label" htmlFor={fieldId}>{label}</label>
      <input id={fieldId} className="field__input" aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined} {...input} />
      {error && <p id={errorId} className="field__error">{error}</p>}
    </div>
  );
}

export function SelectField({ label, error, id, children, ...select }: SelectHTMLAttributes<HTMLSelectElement> & Common) {
  const { fieldId, errorId } = useFieldIds(id);
  return (
    <div className="field">
      <label className="field__label" htmlFor={fieldId}>{label}</label>
      <select id={fieldId} className="field__input" aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined} {...select}>
        {children}
      </select>
      {error && <p id={errorId} className="field__error">{error}</p>}
    </div>
  );
}

export function TextAreaField({ label, error, id, ...area }: TextareaHTMLAttributes<HTMLTextAreaElement> & Common) {
  const { fieldId, errorId } = useFieldIds(id);
  return (
    <div className="field">
      <label className="field__label" htmlFor={fieldId}>{label}</label>
      <textarea id={fieldId} className="field__input" rows={3} aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined} {...area} />
      {error && <p id={errorId} className="field__error">{error}</p>}
    </div>
  );
}
