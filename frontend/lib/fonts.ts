import { Inter, JetBrains_Mono, Space_Grotesk } from "next/font/google";

// Body / UI grotesk
export const fontBody = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

// Display headings — distinctive geometric grotesk, light weights (funda-style)
export const fontDisplay = Space_Grotesk({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-display",
});

// Tabular / data
export const fontMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const fontVars = `${fontBody.variable} ${fontDisplay.variable} ${fontMono.variable}`;
