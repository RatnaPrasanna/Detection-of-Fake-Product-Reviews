import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Review Integrity | Fake Review Risk Analysis",
  description: "Explainable assessment of product review integrity signals.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
