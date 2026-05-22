import type { NextRequest } from "next/server";
import { buildBackendApiUrl, buildBackendErrorResponse } from "../../_lib/backend";

/**
 * Proxy for Python backend static images served at /api/images/*.
 *
 * The FastAPI backend mounts `output/images/` as a StaticFiles directory
 * at `/api/images`.  Because Next.js intercepts all `/api/` paths, a
 * dedicated route handler is required to forward image requests to the
 * Python process and relay the response (JPEG/PNG binary) back to the
 * browser unchanged.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const imagePath = `/images/${path.join("/")}`;

  const backendUrl = buildBackendApiUrl(imagePath, request.nextUrl.search);

  try {
    const response = await fetch(backendUrl, {
      headers: { "Cache-Control": "no-store" },
    });

    const body = await response.arrayBuffer();
    const contentType = response.headers.get("content-type") ?? "image/jpeg";

    return new Response(body, {
      status: response.status,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}
