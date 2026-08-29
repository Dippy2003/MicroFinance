import type { Metadata } from "next";
import "./globals.css";
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";
import { FractalDotGrid } from "@/components/ui/bg-animated-fractal-dot-grid";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

export const metadata: Metadata = {
  title: "MicroLoan AI Agent",
  description: "AI loan advisory for underbanked Sri Lanka",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={cn("dark font-sans", geist.variable)} suppressHydrationWarning>
      <body>
        <div className="fixed inset-0 -z-10">
          <FractalDotGrid
            dotColor="rgba(255, 184, 130, 1)"
            glowColor="rgba(255, 122, 48, 1)"
            dotOpacity={0.35}
            dotSpacing={26}
            dotSize={1.6}
            enableNoise={false}
          />
        </div>
        {children}
      </body>
    </html>
  );
}
