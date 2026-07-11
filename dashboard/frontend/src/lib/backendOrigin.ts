/** Resolve the AgentCheck API / MCP backend origin for the current environment. */
export function getBackendOrigin(): string {
  const configured = import.meta.env.VITE_AGENTCHECK_BACKEND_ORIGIN?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  if (typeof window === "undefined") {
    return "";
  }

  const { protocol, hostname, port, origin } = window.location;
  if (
    (hostname === "localhost" || hostname === "127.0.0.1") &&
    (port === "5173" || port === "4173")
  ) {
    return `${protocol}//${hostname}:8000`;
  }

  return origin;
}

export function backendUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const origin = getBackendOrigin();
  if (!origin) {
    return normalizedPath;
  }
  return new URL(normalizedPath, `${origin}/`).toString();
}
