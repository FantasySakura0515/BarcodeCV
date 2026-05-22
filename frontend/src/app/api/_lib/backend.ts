const BACKEND_API_BASE_URL =
  process.env.BACKEND_API_BASE_URL ??
  "http://127.0.0.1:8000/api";

export function buildBackendApiUrl(path: string, search = "") {
  const normalizedBase = BACKEND_API_BASE_URL.replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}${search}`;
}

export async function relayBackendResponse(response: Response) {
  const body = await response.arrayBuffer();
  const contentType = response.headers.get("content-type");

  return new Response(body, {
    status: response.status,
    headers: contentType ? { "content-type": contentType } : undefined,
  });
}

export function buildBackendErrorResponse(error: unknown) {
  const message = error instanceof Error ? error.message : "Unknown backend error";

  return Response.json(
    {
      detail: `無法連線到後端服務: ${message}`,
    },
    { status: 502 },
  );
}