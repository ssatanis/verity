import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Verity",
  description: "Pre-payment provider integrity for health plans and Medicaid programs, built on public federal data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
