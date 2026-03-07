import { buildBackendApiUrl, buildBackendErrorResponse, relayBackendResponse } from "@/app/api/_lib/backend";

export async function GET() {
  try {
    const response = await fetch(buildBackendApiUrl("/detections"), {
      method: "GET",
      cache: "no-store",
    });

    return relayBackendResponse(response);
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const response = await fetch(buildBackendApiUrl("/detections"), {
      method: "POST",
      body: formData,
      cache: "no-store",
    });

    return relayBackendResponse(response);
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}
