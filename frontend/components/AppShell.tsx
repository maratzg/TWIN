"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";

const navigation = [
  { label: "Overview", href: "/", icon: "⌂", enabled: true },
  { label: "Data", href: "/data", icon: "↥", enabled: true },
  { label: "Documents", href: "/documents", icon: "□", enabled: true },
  { label: "Shipments", href: "/shipments", icon: "▤", enabled: true },
  { label: "Bills of Lading", href: "/bills-of-lading", icon: "▧", enabled: true },
  { label: "Invoices", href: "/invoices", icon: "◇", enabled: true },
  { label: "Analytics", href: "/analytics", icon: "⌁", enabled: true },
  { label: "AI Analyst", icon: "✦", enabled: false },
  { label: "Simulator", icon: "◫", enabled: false },
  { label: "Automations", icon: "↻", enabled: false },
  { label: "Settings", icon: "⚙", enabled: false },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [company, setCompany] = useState("Baltic Freight Demo SIA");
  useEffect(() => {
    api.context<{ name: string }>().then((result) => setCompany(result.name)).catch(() => undefined);
  }, []);
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brandMark">T</span><div><strong>TWIN</strong><small>Logistics intelligence</small></div></div>
        <nav>
          {navigation.map((item) => item.enabled ? (
            <Link key={item.label} href={item.href!} className={pathname === item.href || (item.href !== "/" && pathname.startsWith(`${item.href}/`)) ? "navItem active" : "navItem"}>
              <span>{item.icon}</span>{item.label}
            </Link>
          ) : (
            <div key={item.label} className="navItem disabled" title="Coming later">
              <span>{item.icon}</span>{item.label}<em>Later</em>
            </div>
          ))}
        </nav>
        <div className="tenant"><span className="statusDot"/><div><strong>{company}</strong><small>Development workspace</small></div></div>
      </aside>
      <main className="main">
        <header className="topbar"><div><span className="environment">DETERMINISTIC ANALYTICS v0.4.0</span></div><div className="userBadge">BF</div></header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
