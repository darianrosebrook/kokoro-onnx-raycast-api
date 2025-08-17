/**
 * Navigation component for the dashboard
 * @author @darianrosebrook
 */

"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { DataSourceIndicator } from "@/components/data-source-indicator";

export function Navigation() {
  const pathname = usePathname();

  const navItems = [
    { href: "/", label: "Dashboard", description: "Overview and charts" },
    {
      href: "/benchmarks",
      label: "Benchmarks",
      description: "Detailed results",
    },
  ];

  return (
    <nav className="border-b bg-background">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link href="/" className="text-xl font-bold">
              Kokoro TTS Dashboard
            </Link>
          </div>

          <div className="flex items-center space-x-4">
            <DataSourceIndicator />
            <div className="flex items-center space-x-2">
              {navItems.map((item) => (
                <Button
                  key={item.href}
                  variant={pathname === item.href ? "default" : "ghost"}
                  asChild
                >
                  <Link
                    href={item.href}
                    className="flex flex-col items-center text-center"
                  >
                    <span className="text-sm font-medium">{item.label}</span>
                    <span className="text-xs text-muted-foreground">
                      {item.description}
                    </span>
                  </Link>
                </Button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
