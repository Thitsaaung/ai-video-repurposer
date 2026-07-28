import type { Metadata } from "next";
import { Fraunces, Source_Sans_3 } from "next/font/google";
import AppToaster from "./components/AppToaster";
import "./globals.css";

const display = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
});

const sans = Source_Sans_3({
  variable: "--font-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "T-Clipper",
  description:
    "Turn YouTube videos into ready-to-post vertical clips with AI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${sans.variable} antialiased`}>
        {children}
        <AppToaster />
      </body>
    </html>
  );
}
