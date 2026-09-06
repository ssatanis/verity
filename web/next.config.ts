import type { NextConfig } from "next";
// Defense in depth for every response: no MIME sniffing, no framing by other sites, a tight referrer policy, no browser
// features the console does not use, and HSTS once the site is served over HTTPS (browsers ignore it on plain http).
const security = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
];
const nextConfig: NextConfig = {
  poweredByHeader: false,
  // The static fallback JSON is read with fs at request time, so it must ride along in every serverless function bundle.
  // The PDF route loads the Garamond and Open Sans files from @fontsource at render time; nothing imports them, so the tracer
  // must be told to ship them with that function or the route fails in production with ENOENT.
  outputFileTracingIncludes: { "/**": ["./public/fallback/**"], "/api/packets/[id]/pdf": ["./node_modules/@fontsource/eb-garamond/files/*", "./node_modules/@fontsource/open-sans/files/*", "./node_modules/pdfkit/js/**", "./node_modules/@react-pdf/**"] },
  async headers() { return [{ source: "/(.*)", headers: security }]; },
};
export default nextConfig;
