"use client";

import { SessionProvider } from "next-auth/react";
import { SettingsProvider } from "@/contexts/settings-context";
import { SidebarProvider } from "@/components/ui/sidebar";
import type { LocaleType } from "@/types";

export function Providers({ children, locale = "en" }: { children: React.ReactNode, locale?: string }) {
  return (
    <SettingsProvider locale={locale as LocaleType}>
      <SessionProvider>
        <SidebarProvider>
          {children}
        </SidebarProvider>
      </SessionProvider>
    </SettingsProvider>
  );
}
