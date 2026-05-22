import { buildBackendApiUrl, buildBackendErrorResponse, relayBackendResponse } from "@/app/api/_lib/backend";

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    let response = await fetch(buildBackendApiUrl("/live-preview-detection"), {
      method: "POST",
      body: formData,
      cache: "no-store",
    });

    if (response.status === 404) {
      response = await fetch(buildBackendApiUrl("/detections/preview"), {
        method: "POST",
        body: formData,
        cache: "no-store",
      });
    }

    return relayBackendResponse(response);
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}