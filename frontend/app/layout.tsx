import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "RAG Knowledge Base",
  description: "A local RAG question answering workspace for a personal knowledge base."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
