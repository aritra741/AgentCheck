import { useMemo } from "react";

interface ResponseDiffProps {
  clean: Record<string, unknown>;
  injected: Record<string, unknown>;
}

function flattenKeys(obj: Record<string, unknown>, prefix = ""): string[] {
  const keys: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    keys.push(path);
    if (value && typeof value === "object" && !Array.isArray(value)) {
      keys.push(...flattenKeys(value as Record<string, unknown>, path));
    }
  }
  return keys;
}

function getAtPath(obj: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, part) => {
    if (acc && typeof acc === "object" && !Array.isArray(acc)) {
      return (acc as Record<string, unknown>)[part];
    }
    return undefined;
  }, obj);
}

function formatValue(value: unknown): string {
  if (value === undefined) return "(missing)";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

export function ResponseDiff({ clean, injected }: ResponseDiffProps) {
  const rows = useMemo(() => {
    const allKeys = new Set([
      ...flattenKeys(clean),
      ...flattenKeys(injected),
    ]);
    return Array.from(allKeys).map((key) => {
      const cleanVal = getAtPath(clean, key);
      const injectedVal = getAtPath(injected, key);
      const changed =
        JSON.stringify(cleanVal) !== JSON.stringify(injectedVal);
      return { key, cleanVal, injectedVal, changed };
    });
  }, [clean, injected]);

  const hasStructuredDiff = rows.some((r) => r.changed);

  if (!hasStructuredDiff) {
    return (
      <div className="response-pair">
        <div>
          <div className="response-label">Clean response</div>
          <pre className="response-box clean">{formatValue(clean)}</pre>
        </div>
        <div>
          <div className="response-label">Injected response</div>
          <pre className="response-box injected">{formatValue(injected)}</pre>
        </div>
      </div>
    );
  }

  return (
    <div className="response-diff-table-wrap">
      <table className="response-diff-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Clean</th>
            <th>Injected</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className={row.changed ? "diff-changed" : ""}>
              <td className="diff-key">{row.key}</td>
              <td>
                <div className="diff-val">{formatValue(row.cleanVal)}</div>
              </td>
              <td>
                <div className="diff-val">{formatValue(row.injectedVal)}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
