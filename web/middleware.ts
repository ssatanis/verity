import { NextResponse, type NextRequest } from "next/server";

// Console gate: /app and the write routes require a signed session cookie set by /login. Public pages: landing, legal, /login.
async function hmac(value: string, secret: string) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value));
  return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, "0")).join("");
}
export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const gated = pathname.startsWith("/app") || pathname.startsWith("/api/");
  if (!gated || pathname.startsWith("/api/login")) return NextResponse.next();
  const secret = process.env.VERITY_SESSION_SECRET ?? ""; const pw = process.env.VERITY_CONSOLE_PASSWORD ?? "";
  if (!pw) return NextResponse.next(); // no password configured: open (local development)
  const c = req.cookies.get("verity_session")?.value ?? "";
  const expected = await hmac("console:" + pw, secret);
  if (c === expected) return NextResponse.next();
  if (pathname.startsWith("/api/")) return NextResponse.json({ error: "sign in required" }, { status: 401 });
  const url = req.nextUrl.clone(); url.pathname = "/login"; url.searchParams.set("next", pathname); return NextResponse.redirect(url);
}
export const config = { matcher: ["/app/:path*", "/api/:path*"] };
