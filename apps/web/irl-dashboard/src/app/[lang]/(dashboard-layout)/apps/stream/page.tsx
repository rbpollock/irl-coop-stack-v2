"use client"

import { useRef, useState } from "react"
import Hls from "hls.js"
import { MonitorPlay, Play } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

// The HLS stream is proxied same-origin through /api/stream, which adds the
// viewer's coop JWT server-side for MediaMTX's JWT auth — the browser never
// talks to stream.irl.coop directly and never holds the auth header.
const PROXY_BASE = "/api/stream"

export default function StreamPage() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const hlsRef = useRef<Hls | null>(null)
  const [path, setPath] = useState("live/demo")
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const stop = () => {
    hlsRef.current?.destroy()
    hlsRef.current = null
    if (videoRef.current) videoRef.current.src = ""
    setPlaying(false)
  }

  const play = () => {
    const video = videoRef.current
    if (!video) return
    stop()
    setError(null)

    const src = `${PROXY_BASE}/${path.replace(/^\/+/, "")}/index.m3u8`

    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true })
      hls.loadSource(src)
      hls.attachMedia(video)
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (!data.fatal) return
        const msg =
          data.type === Hls.ErrorTypes.NETWORK_ERROR
            ? "Could not load the stream — is it live? (A network error usually means no stream is publishing at that path.)"
            : data.type === Hls.ErrorTypes.MEDIA_ERROR
              ? "The stream is not playable in this browser."
              : "Failed to play the stream."
        setError(msg)
        stop()
      })
      hlsRef.current = hls
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src // Safari native HLS
    } else {
      setError("This browser does not support HLS playback.")
      return
    }

    video.play().catch(() => setError("Autoplay was blocked — press play on the player."))
    setPlaying(true)
  }

  return (
    <div className="flex h-[calc(100svh-9.85rem)] flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Live Video</h1>
          <p className="text-xs text-muted-foreground">
            Watch a coop stream — enter the path it was published to (e.g.{" "}
            <code className="font-mono">live/demo</code>).
          </p>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-center gap-2">
          <Input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="live/demo"
            className="max-w-xs font-mono"
          />
          <Button size="sm" onClick={playing ? stop : play}>
            <Play className="me-1.5 h-3.5 w-3.5" />
            {playing ? "Stop" : "Play"}
          </Button>
        </div>

        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <MonitorPlay className="h-4 w-4 shrink-0" />
            {error}
          </p>
        )}

        <div className="flex-1 overflow-hidden rounded-lg border bg-black">
          <video ref={videoRef} controls className="h-full w-full" playsInline />
        </div>
      </div>
    </div>
  )
}
