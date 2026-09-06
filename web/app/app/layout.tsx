import { Nav } from "@/components/landing/Nav";
import { Footer } from "@/components/landing/Footer";
// The console shares the landing page's header and footer exactly; the header shows the console's section links and the provider search
// in the slot the landing page uses for its Console link.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <Nav mode="console" />
      <main className="max-w-[1280px] mx-auto px-4 md:px-6 py-8 w-full flex-1">{children}</main>
      <Footer />
    </div>
  );
}
