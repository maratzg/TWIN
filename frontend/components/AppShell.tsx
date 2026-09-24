"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const navigation = [
  { label: "Overview", href: "/", icon: "⌂", enabled: true },
  { label: "Data", href: "/data", icon: "↥", enabled: true },
  { label: "Documents", icon: "□", enabled: false },
  { label: "Shipments", href: "/shipments", icon: "▤", enabled: true },
  { label: "Finance", icon: "◇", enabled: false },
  { label: "Analytics", icon: "⌁", enabled: false },
  { label: "AI Analyst", icon: "✦", enabled: false },
  { label: "Simulator", icon: "◫", enabled: false },
  { label: "Automations", icon: "↻", enabled: false },
  { label: "Settings", icon: "⚙", enabled: false },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brandMark">T</span><div><strong>TWIN</strong><small>Logistics intelligence</small></div></div>
        <nav>
          {navigation.map((item) => item.enabled ? (
            <Link key={item.label} href={item.href!} className={pathname === item.href ? "navItem active" : "navItem"}>
              <span>{item.icon}</span>{item.label}
            </Link>
          ) : (
            <div key={item.label} className="navItem disabled" title="Coming later">
              <span>{item.icon}</span>{item.label}<em>Later</em>
            </div>
          ))}
        </nav>
        <div className="tenant"><span className="statusDot"/><div><strong>Demo Logistics SIA</strong><small>Development workspace</small></div></div>
      </aside>
      <main className="main">
        <header className="topbar"><div><span className="environment">REVIEW WORKBENCH v0.2</span></div><div className="userBadge">DL</div></header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
