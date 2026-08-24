import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: "Finbot",
  description: "An AI financial analyst over 8.9 million labeled card transactions.",
};

export const viewport = { themeColor: "#010102" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" className={`${sans.variable} ${mono.variable}`}>
      <head>
        {/* Applies the saved theme before first paint, otherwise a dark-mode user sees
            a flash of the light theme on every load. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("finbot-theme");if(t==="dark"){document.documentElement.dataset.theme="dark";document.documentElement.classList.add("dark")}}catch(e){}`,
          }}
        />
      </head>
      <body>
        <CopilotKitProvider runtimeUrl="/api/copilotkit">{children}</CopilotKitProvider>
      </body>
    </html>
  );
}
