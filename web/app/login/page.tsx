"use client";
import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import { Logo } from "@/components/landing/Logo";
function Form() {
  const sp = useSearchParams(); const router = useRouter();
  const [pw, setPw] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function go(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: pw, next: sp.get("next") ?? "/app" }) });
    const j = await r.json(); setBusy(false);
    if (r.ok) router.push(j.next); else setErr(j.error ?? "Sign in failed");
  }
  return (
    <form onSubmit={go} className="card p-8 w-full max-w-sm">
      <Logo size={30} />
      <h1 className="serif text-[34px] mt-8 leading-none">Reviewer sign in</h1>
      <p className="text-[13px] text-[var(--ink-3)] mt-3">The console lists referral candidates by name. Access is limited to reviewers who have agreed to treat every row as an indicator to verify, not a finding.</p>
      <input type="password" value={pw} onChange={e => setPw(e.target.value)} placeholder="Console password" className="w-full mt-6" autoFocus />
      {err && <div className="text-[12px] mt-2" style={{ color: "var(--danger)" }}>{err}</div>}
      <button className="btn w-full mt-4 justify-center" disabled={busy}>{busy ? "Signing in" : "Enter console"}</button>
    </form>
  );
}
export default function Login() {
  return <main className="min-h-screen grid place-items-center px-6" style={{ background: "var(--paper-2)" }}><Suspense><Form /></Suspense></main>;
}
