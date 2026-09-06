import type { Metadata } from "next";
import "./globals.css";
import { CommandPalette } from "@/components/app/CommandPalette";

export const metadata: Metadata = {
  title: "Verity",
  description: "Pre-payment provider integrity for health plans and Medicaid programs, built on public federal data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>{children}<CommandPalette /></body>
    </html>
  );
}
