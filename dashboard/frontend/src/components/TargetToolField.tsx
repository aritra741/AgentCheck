import type { ReactNode } from "react";

export interface ToolChoice {
  value: string;
  name: string;
}

interface TargetToolFieldProps {
  value: string;
  onChange: (value: string) => void;
  choices?: ToolChoice[];
  helperText: ReactNode;
  placeholder?: string;
}

export function TargetToolField({
  value,
  onChange,
  choices,
  helperText,
  placeholder = "search_docs",
}: TargetToolFieldProps) {
  const controlClassName = choices
    ? "field-select target-tool-control"
    : "field-input target-tool-control";

  return (
    <div className="form-field target-tool-field">
      <label htmlFor="target-tool">Tool to inject into</label>
      {choices ? (
        <select
          id="target-tool"
          className={controlClassName}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          title={value}
        >
          {choices.map((tool) => (
            <option key={tool.value} value={tool.value}>
              {tool.value}
            </option>
          ))}
        </select>
      ) : (
        <input
          id="target-tool"
          className={controlClassName}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
        />
      )}
      <p className="config-footer-note">{helperText}</p>
    </div>
  );
}
