import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Sets <title> and <meta name="description"> for every page (pages can override).
export const metadata: Metadata = {
  title: "TradeQuote",
  description: "Quotes and job tracking for trade contractors.",
};

// The root layout wraps every page. `LayoutProps<"/">` is a type Next.js
// generates from our routes (via `next dev`, `next build`, or `next typegen`),
// so `children` is typed without us writing the props interface by hand.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
