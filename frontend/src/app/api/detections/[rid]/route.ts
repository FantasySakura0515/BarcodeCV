import { buildBackendApiUrl, buildBackendErrorResponse, relayBackendResponse } from "@/app/api/_lib/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ rid: string }> },
) {
  try {
    const { rid } = await context.params;
    const response = await fetch(buildBackendApiUrl(`/detections/${rid}`), {
      method: "GET",
      cache: "no-store",
    });

    return relayBackendResponse(response);
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}
