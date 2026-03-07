import type { NextConfig } from "next";

// Parse the backend hostname/port from BACKEND_API_BASE_URL so that
// next/image is allowed to load images from the backend, even when it
// runs on a Raspberry Pi with an arbitrary IP address.
function backendRemotePattern(): import("next").RemotePattern {
  const raw = process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000/api";
  try {
    const url = new URL(raw);
    return {
      protocol: url.protocol.replace(":", "") as "http" | "https",
      hostname: url.hostname,
      port: url.port || undefined,
    };
  } catch {
    return { protocol: "http", hostname: "127.0.0.1", port: "8000" };
  }
}

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      backendRemotePattern(),
      // Always allow localhost for local dev
      { protocol: "http", hostname: "127.0.0.1", port: "8000" },
      { protocol: "http", hostname: "localhost", port: "8000" },
      { protocol: "https", hostname: "images.unsplash.com" },
    ],
  },
};

export default nextConfig;
