import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GDG İstinye Campus Platform",
  description: "İstinye University student platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <header className="border-b">
          <nav className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
            <span className="font-semibold">GDG İstinye</span>
            <div className="flex gap-4 text-sm text-muted-foreground">
              <span>Listings</span>
              <span>Notes</span>
              <span>Profile</span>
            </div>
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
