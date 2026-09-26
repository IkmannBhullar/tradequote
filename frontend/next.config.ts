import path from "node:path";

import type { NextConfig } from "next";

// This folder IS the project root. Pinning it stops Next.js from guessing a
// "workspace root" by searching parent folders for lockfiles (a stray
// package-lock.json in a home directory would otherwise be picked up).
const projectRoot = path.resolve(__dirname);

const nextConfig: NextConfig = {
  reactCompiler: true,
  outputFileTracingRoot: projectRoot,
  turbopack: { root: projectRoot },
  // Client quote pages carry a secret token in their URL. Don't let
  // browsers or proxies cache them, search engines index them, or the URL
  // leak to other sites through the Referer header.
  async headers() {
    return [
      {
        source: "/q/:path*",
        headers: [
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
          { key: "Cache-Control", value: "private, no-store" },
        ],
      },
    ];
  },
};

export default nextConfig;
