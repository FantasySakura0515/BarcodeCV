const isBrowser = typeof window !== "undefined";

const API_BASE_URL = isBrowser
  ? "/api"
  : process.env.FRONTEND_INTERNAL_API_BASE_URL ?? "http://127.0.0.1:3000/api";

export function getApiBaseUrl() {
  return API_BASE_URL;
}

export function getBackendOrigin() {
  if (API_BASE_URL.startsWith("/")) {
    return "";
  }

  return API_BASE_URL.replace(/\/api\/?$/, "");
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