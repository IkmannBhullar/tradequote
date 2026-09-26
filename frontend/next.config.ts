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
};

export default nextConfig;
