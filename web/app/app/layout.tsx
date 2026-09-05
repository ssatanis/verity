import { ConsoleNav } from "@/components/app/ConsoleNav";
import { Footer } from "@/components/landing/Footer";
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <ConsoleNav />
      <main className="max-w-[1280px] mx-auto px-4 md:px-6 py-8 w-full flex-1">{children}</main>
      <Footer />
    </div>
  );
}
