import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "SkillSwap — Campus Peer Skill Exchange",
  description: "Credit-based peer-to-peer time-banking skill exchange platform for university students.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased font-sans">
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  );
}
