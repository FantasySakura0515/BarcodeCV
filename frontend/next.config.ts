import type { NextConfig } from "next";

// Parse the backend hostname/port from BACKEND_API_BASE_URL so that
// next/image is allowed to load images from the backend, even when it
// runs on a Raspberry Pi with an arbitrary IP address.
function backendRemotePattern() {
  const raw = process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000/api";
  try {
    const url = new URL(raw);
    return {
      protocol: url.protocol.replace(":", "") as "http" | "https",
      hostname: url.hostname,
      ...(url.port ? { port: url.port } : {}),
    };
  } catch {
    return { protocol: "http" as const, hostname: "127.0.0.1", port: "8000" };
  }
}

const nextConfig: NextConfig = {
  transpilePackages: ["tailwindcss"],
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
