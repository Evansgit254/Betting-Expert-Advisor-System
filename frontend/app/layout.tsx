export const metadata = {
  title: 'Betting Expert Advisor',
  description: 'Enterprise dashboard for Betting Expert Advisor',
};

import './globals.css';
import React from 'react';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        <div className="mx-auto max-w-7xl px-4 py-6">
          <header className="mb-6 flex items-center justify-between">
            <h1 className="text-xl font-semibold">Betting Expert Advisor</h1>
            <nav className="flex gap-4 text-sm">
              <a href="/" className="hover:underline">Dashboard</a>
              <a href="/odds" className="hover:underline">Odds</a>
              <a href="/bets" className="hover:underline">Bets</a>
              <a href="/arbitrage" className="hover:underline">Arbitrage</a>
              <a href="/social-signals" className="hover:underline">Social Signals</a>
              <a href="/strategy" className="hover:underline">Strategy</a>
              <a href="/health" className="hover:underline">Health</a>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
