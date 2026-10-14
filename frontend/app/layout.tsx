import type { Metadata } from "next";
import { DevAgentation } from "@/components/dev-agentation";
import "@fontsource-variable/vazirmatn";
import "katex/dist/katex.min.css";
import "./globals.css";
import "@/components/blocks/blocks.css";
export const metadata: Metadata = { title: "هم‌درس | MathTutor", description: "یادگیری ریاضی، با سرعت و زبان شما" };
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="fa" dir="rtl" suppressHydrationWarning><body>{children}{process.env.NODE_ENV === "development" && <DevAgentation />}</body></html>;
}
