import { buildBackendApiUrl, buildBackendErrorResponse } from "@/app/api/_lib/backend";

// Never cache; always fetch from backend on every request.
export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  context: { params: Promise<{ cameraId: string }> },
) {
  try {
    const { cameraId } = await context.params;
    const search = new URL(request.url).search;

    const response = await fetch(buildBackendApiUrl(`/cameras/${cameraId}/stream`, search), {
      method: "GET",
      cache: "no-store",
      // No timeout / AbortSignal — stream runs indefinitely until client disconnects.
    });

    if (!response.ok || !response.body) {
      return new Response("stream not available", { status: response.status || 503 });
    }

    // Relay the ReadableStream body directly — do NOT buffer with arrayBuffer()
    // because MJPEG is an infinite-length multipart response.
    return new Response(response.body, {
      status: 200,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ??
          "multipart/x-mixed-replace; boundary=frame",
        "Cache-Control": "no-cache, no-store",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
      },
    });
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}
