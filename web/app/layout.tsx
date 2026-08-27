import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { SkipLink } from "@/components/skip-link";
import { OfflineBanner } from "@/components/offline-banner";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
  preload: false,
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "https://upgrade.app"
  ),
  title: {
    default: "UpGrade — Master Any Subject Fast",
    template: "%s | UpGrade",
  },
  description:
    "AI-powered personalized roadmaps, JIT micro-learning feeds, and interactive topic doubts.",
  keywords: [
    "AI learning",
    "personalized roadmaps",
    "bite-sized learning",
    "just-in-time feed",
    "curriculum generator",
  ],
  authors: [{ name: "UpGrade Team" }],
  creator: "UpGrade",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://upgrade.app",
    siteName: "UpGrade",
    title: "UpGrade — Master Any Subject Fast",
    description:
      "AI-powered personalized roadmaps, JIT micro-learning feeds, and interactive topic doubts.",
  },
  twitter: {
    card: "summary_large_image",
    title: "UpGrade — Master Any Subject Fast",
    description:
      "AI-powered personalized roadmaps, JIT micro-learning feeds, and interactive topic doubts.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#09090b",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable}`}
      style={{ colorScheme: "dark" }}
    >
      <body className="min-h-screen bg-background font-sans text-foreground antialiased selection:bg-primary/10">
        <SkipLink targetId="main-content" />
        <OfflineBanner />
        {children}
        <Toaster richColors closeButton position="top-right" />
      </body>
    </html>
  );
}
