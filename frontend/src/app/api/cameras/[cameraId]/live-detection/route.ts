import { buildBackendApiUrl, buildBackendErrorResponse, relayBackendResponse } from "@/app/api/_lib/backend";

export async function GET(
  request: Request,
  context: { params: Promise<{ cameraId: string }> },
) {
  try {
    const { cameraId } = await context.params;
    const search = new URL(request.url).search;
    const response = await fetch(buildBackendApiUrl(`/cameras/${cameraId}/live-detection`, search), {
      method: "GET",
      cache: "no-store",
    });

    return relayBackendResponse(response);
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}