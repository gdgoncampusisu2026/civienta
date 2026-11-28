import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Civienta",
  description: "Campus platform for Istinye University students",
};

const navLinks = [
  { href: "/listings", label: "Listings" },
  { href: "/notes", label: "Notes" },
  { href: "/profile", label: "Profile" },
];

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
            <Link href="/" className="font-semibold">
              Civienta
            </Link>
            <div className="flex gap-4 text-sm text-muted-foreground">
              {navLinks.map(({ href, label }) => (
                <Link key={href} href={href} className="hover:text-foreground">
                  {label}
                </Link>
              ))}
            </div>
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
