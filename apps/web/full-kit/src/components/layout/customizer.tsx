"use client"

import { useCallback } from "react"
import { useParams, usePathname, useRouter } from "next/navigation"
import {
  AlignLeft,
  AlignRight,
  AlignStartHorizontal,
  AlignStartVertical,
  MoonStar,
  RotateCcw,
  Settings,
  Sun,
  SunMoon,
} from "lucide-react"

import type { LocaleType, ModeType, ThemeType } from "@/types"
import type { CSSProperties } from "react"

import { i18n } from "@/configs/i18n"
import { radii, themes } from "@/configs/themes"
import { relocalizePathname } from "@/lib/i18n"

import { useSettings } from "@/hooks/use-settings"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetPortal,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"

export function Customizer() {
  const { settings, updateSettings, resetSettings } = useSettings()
  const pathname = usePathname()
  const router = useRouter()
  const params = useParams()

  const locale = params.lang as LocaleType
  const direction = i18n.localeDirection[locale]

  const handleSetLocale = useCallback(
    (localeName: LocaleType) => {
      updateSettings({ ...settings, locale: localeName })
      router.push(relocalizePathname(pathname, localeName))
    },
    [settings, updateSettings, router, pathname]
  )

  const handleSetMode = useCallback(
    (modeName: ModeType) => {
      updateSettings({ ...settings, mode: modeName })
    },
    [settings, updateSettings]
  )

  const handleReset = useCallback(() => {
    resetSettings()
    router.push(relocalizePathname(pathname, "en"), { scroll: false })
  }, [resetSettings, router, pathname])

  return (
    <Sheet>
      <SheetTrigger className="fixed bottom-10 end-0 z-50" asChild>
        <Button
          size="icon"
          className="rounded-e-none shadow-sm"
          aria-label="Customizer"
        >
          <Settings className="shrink-0 h-4 w-4" />
        </Button>
      </SheetTrigger>
      <SheetPortal>
        <SheetContent className="p-0" side="end">
          <ScrollArea className="h-full p-4">
            <div className="flex flex-1 flex-col space-y-4">
              <SheetHeader>
                <SheetTitle>Customizer</SheetTitle>
                <SheetDescription>
                  Pick a style and color for the dashboard.
                </SheetDescription>
              </SheetHeader>
              <div className="space-y-1.5">
                <p className="text-sm">Color</p>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(themes).map(([name, value]) => {
                    const isActive = settings.theme === name

                    return (
                      <Button
                        key={name}
                        variant={isActive ? "secondary" : "default"}
                        style={
                          {
                            "--primary":
                              value.activeColor[
                                settings.mode === "dark" ? "dark" : "light"
                              ],
                            "--primary-foreground":
                              value.activeColor["foreground"],
                          } as CSSProperties
                        }
                        onClick={() =>
                          updateSettings({
                            ...settings,
                            theme: name as ThemeType,
                          })
                        }
                      >
                        <span>{value.label}</span>
                      </Button>
                    )
                  })}
                </div>
              </div>
              <div className="space-y-1.5">
                <p className="text-sm">Radius</p>
                <div className="grid grid-cols-5 gap-2">
                  {radii.map((value) => (
                    <Button
                      variant={
                        settings.radius === value ? "secondary" : "outline"
                      }
                      key={value}
                      onClick={() => {
                        updateSettings({
                          ...settings,
                          radius: value,
                        })
                      }}
                    >
                      {value}
                    </Button>
                  ))}
                </div>
              </div>
              <div className="space-y-1.5">
                <p className="text-sm">Mode</p>
                <div className="grid grid-cols-3 gap-2">
                  <Button
                    variant={
                      settings.mode === "light" ? "secondary" : "outline"
                    }
                    onClick={() => handleSetMode("light")}
                  >
                    <Sun className="shrink-0 h-4 w-4 me-2" />
                    Light
                  </Button>
                  <Button
                    variant={settings.mode === "dark" ? "secondary" : "outline"}
                    onClick={() => handleSetMode("dark")}
                  >
                    <MoonStar className="shrink-0 h-4 w-4 me-2" />
                    Dark
                  </Button>
                  <Button
                    variant={
                      settings.mode === "system" ? "secondary" : "outline"
                    }
                    onClick={() => handleSetMode("system")}
                  >
                    <SunMoon className="shrink-0 h-4 w-4 me-2" />
                    System
                  </Button>
                </div>
                <div className="space-y-1.5">
                  <span className="text-sm">Layout</span>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      variant={
                        settings.layout === "horizontal"
                          ? "secondary"
                          : "outline"
                      }
                      onClick={() =>
                        updateSettings({
                          ...settings,
                          layout: "horizontal",
                        })
                      }
                    >
                      <AlignStartHorizontal className="shrink-0 h-4 w-4 me-2" />
                      Horizontal
                    </Button>
                    <Button
                      variant={
                        settings.layout === "vertical" ? "secondary" : "outline"
                      }
                      onClick={() =>
                        updateSettings({
                          ...settings,
                          layout: "vertical",
                        })
                      }
                    >
                      <AlignStartVertical className="shrink-0 h-4 w-4 me-2" />
                      Vertical
                    </Button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <span className="text-sm">Direction</span>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      variant={direction === "ltr" ? "secondary" : "outline"}
                      onClick={() => handleSetLocale("en")}
                    >
                      <AlignLeft className="shrink-0 h-4 w-4 me-2" />
                      LRT
                    </Button>
                    <Button
                      variant={direction === "rtl" ? "secondary" : "outline"}
                      onClick={() => handleSetLocale("ar")}
                    >
                      <AlignRight className="shrink-0 h-4 w-4 me-2" />
                      RTL
                    </Button>
                  </div>
                </div>
              </div>

              <Button
                variant="outline"
                className="w-full"
                onClick={handleReset}
              >
                <RotateCcw className="shrink-0 h-4 w-4 me-2" />
                Reset
              </Button>
            </div>
          </ScrollArea>
        </SheetContent>
      </SheetPortal>
    </Sheet>
  )
}
