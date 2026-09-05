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
  async headers() { return [{ source: "/(.*)", headers: security }]; },
};
export default nextConfig;
