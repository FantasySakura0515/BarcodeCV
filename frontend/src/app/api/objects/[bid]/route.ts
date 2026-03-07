import { buildBackendApiUrl, buildBackendErrorResponse, relayBackendResponse } from "@/app/api/_lib/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ bid: string }> },
) {
  try {
    const { bid } = await context.params;
    const response = await fetch(buildBackendApiUrl(`/objects/${bid}`), {
      method: "GET",
      cache: "no-store",
    });

    return relayBackendResponse(response);
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ bid: string }> },
) {
  try {
    const { bid } = await context.params;
    const payload = await request.text();
    const response = await fetch(buildBackendApiUrl(`/objects/${bid}`), {
      method: "PATCH",
      headers: {
        "content-type": request.headers.get("content-type") ?? "application/json",
      },
      body: payload,
      cache: "no-store",
    });

    return relayBackendResponse(response);
  } catch (error) {
    return buildBackendErrorResponse(error);
  }
}
