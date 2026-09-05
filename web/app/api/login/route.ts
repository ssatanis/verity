import { NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";
export async function POST(req: Request) {
  const { password, next = "/app" } = await req.json();
  const pw = process.env.VERITY_CONSOLE_PASSWORD ?? ""; const secret = process.env.VERITY_SESSION_SECRET ?? "";
  const a = Buffer.from(String(password ?? "")), b = Buffer.from(pw);
  if (!pw || a.length !== b.length || !timingSafeEqual(a, b)) return NextResponse.json({ error: "That password is not right." }, { status: 401 });
  const token = createHmac("sha256", secret).update("console:" + pw).digest("hex");
  const res = NextResponse.json({ ok: true, next });
  res.cookies.set("verity_session", token, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 60 * 60 * 24 * 14 });
  return res;
}
export async function DELETE() { const res = NextResponse.json({ ok: true }); res.cookies.set("verity_session", "", { path: "/", maxAge: 0 }); return res; }
