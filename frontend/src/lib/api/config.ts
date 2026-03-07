const isBrowser = typeof window !== "undefined";

// Server-side (Next.js API routes): proxy to the Python backend.
// Set BACKEND_API_BASE_URL to point to the Pi when frontend is on a different machine.
// e.g. BACKEND_API_BASE_URL=http://192.168.1.100:8000/api
//
// Browser-side: always use relative /api so the browser hits the Next.js proxy.
const API_BASE_URL = isBrowser
  ? "/api"
  : process.env.FRONTEND_INTERNAL_API_BASE_URL ?? "http://127.0.0.1:3000/api";

// Resolve the origin of the Python backend for constructing image URLs.
// Set NEXT_PUBLIC_BACKEND_ORIGIN when frontend and backend are on different hosts.
// e.g. NEXT_PUBLIC_BACKEND_ORIGIN=http://192.168.1.100:8000
const BACKEND_ORIGIN: string = (() => {
  if (process.env.NEXT_PUBLIC_BACKEND_ORIGIN) {
    return process.env.NEXT_PUBLIC_BACKEND_ORIGIN.replace(/\/$/, "");
  }
  // Fall back: derive from BACKEND_API_BASE_URL (server env, available at build time)
  const raw = process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000/api";
  try {
    const url = new URL(raw);
    return `${url.protocol}//${url.host}`;
  } catch {
    return "http://127.0.0.1:8000";
  }
})();

export function getApiBaseUrl() {
  return API_BASE_URL;
}

export function getBackendOrigin() {
  if (!isBrowser) {
    return BACKEND_ORIGIN;
  }
  // In the browser, images are always served via the Next.js proxy origin
  return "";
}

export function resolveApiAssetUrl(path: string | null | undefined) {
  if (!path) {
    return null;
  }

  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  return `${getBackendOrigin()}${path.startsWith("/") ? path : `/${path}`}`;
}