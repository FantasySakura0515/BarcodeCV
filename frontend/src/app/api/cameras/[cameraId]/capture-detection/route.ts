import { buildBackendApiUrl, buildBackendErrorResponse, relayBackendResponse } from "@/app/api/_lib/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ cameraId: string }> },
) {
  try {
    const { cameraId } = await context.params;
    const formData = await request.formData();
    const response = await fetch(buildBackendApiUrl(`/cameras/${cameraId}/capture-detection`), {
      method: "POST",
      body: formData,
      cache: "no-store",
    });

    return relayBackendResponse(response);
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}