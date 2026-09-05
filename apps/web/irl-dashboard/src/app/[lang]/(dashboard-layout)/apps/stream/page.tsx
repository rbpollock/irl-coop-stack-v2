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
  const [broadcasting, setBroadcasting] = useState(false)
  const [streamerMode, setStreamerMode] = useState(false)
  const [shareModalOpen, setShareModalOpen] = useState(false)
  const [matrixLiveCallActive, setMatrixLiveCallActive] = useState(false)

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

  const toggleBroadcast = async () => {
    if (broadcasting) {
      setBroadcasting(false)
      return
    }
    try {
      const mediaStream = await navigator.mediaDevices.getDisplayMedia({
        video: { displaySurface: "browser" },
        audio: true,
      })
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
        videoRef.current.muted = true
        videoRef.current.play()
      }
      setBroadcasting(true)
      mediaStream.getVideoTracks()[0].onended = () => {
        setBroadcasting(false)
        if (videoRef.current) videoRef.current.srcObject = null
      }
    } catch (e: any) {
      setError(e.message || "Failed to start screen share.")
    }
  }

  const toggleMatrixLiveCall = () => {
    setMatrixLiveCallActive(!matrixLiveCallActive)
  }

  return (
    <div className={`flex h-[calc(100svh-9.85rem)] flex-col ${streamerMode ? "ring-4 ring-rose-500/30" : ""}`}>
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold flex items-center gap-2">
            Live Video & Sovereign Stream
            {streamerMode && <span className="rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-medium text-rose-500">Streamer Mode Active</span>}
          </h1>
          <p className="text-xs text-muted-foreground">
            Sovereign streaming via MediaMTX & Matrix LiveKit calls.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={streamerMode ? "default" : "outline"}
            onClick={() => setStreamerMode(!streamerMode)}
            className="text-xs"
          >
            {streamerMode ? "Hide Sensitive UI" : "Streamer Privacy"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              const url = window.location.href.split("?")[0] + `?path=${encodeURIComponent(path)}`
              navigator.clipboard.writeText(url)
              alert("Shareable link copied to clipboard!")
            }}
            className="text-xs"
          >
            Share Link
          </Button>
          <Button
            size="sm"
            variant={matrixLiveCallActive ? "default" : "secondary"}
            onClick={toggleMatrixLiveCall}
            className="text-xs"
          >
            {matrixLiveCallActive ? "Exit Matrix Call" : "Matrix Video Call"}
          </Button>
          <Button
            size="sm"
            variant={broadcasting ? "destructive" : "default"}
            onClick={toggleBroadcast}
            className="text-xs"
          >
            {broadcasting ? "Stop Sharing" : "Go Live (Screen Share)"}
          </Button>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="live/demo"
              className="max-w-xs font-mono"
            />
            <Button size="sm" onClick={playing ? stop : play}>
              <Play className="me-1.5 h-3.5 w-3.5" />
              {playing ? "Stop" : "Play HLS"}
            </Button>
          </div>
          {broadcasting && (
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-500 animate-pulse">
              <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
              Broadcasting Browser Screen
            </div>
          )}
        </div>

        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <MonitorPlay className="h-4 w-4 shrink-0" />
            {error}
          </p>
        )}

        <div className="grid flex-1 grid-cols-1 md:grid-cols-3 gap-4 overflow-hidden">
          <div className="md:col-span-2 flex flex-col overflow-hidden rounded-lg border bg-black relative">
            <video ref={videoRef} controls className="h-full w-full object-contain" playsInline />
            {matrixLiveCallActive && (
              <div className="absolute inset-0 bg-background/95 backdrop-blur flex flex-col items-center justify-center p-6 text-center">
                <h3 className="text-base font-semibold mb-2">Matrix LiveKit Video Call Stage</h3>
                <p className="text-xs text-muted-foreground mb-4 max-w-md">
                  Connected to Matrix SFU stage. All participants in this group room can broadcast or view the sovereign feed.
                </p>
                <div className="w-full h-64 rounded border bg-card flex items-center justify-center text-xs text-muted-foreground">
                  [LiveKit Stage Grid — Active Speaker & Stream Overlay]
                </div>
                <Button size="sm" variant="outline" className="mt-4" onClick={toggleMatrixLiveCall}>
                  Return to Stream Viewer
                </Button>
              </div>
            )}
          </div>

          <div className="flex flex-col rounded-lg border bg-card overflow-hidden">
            <div className="border-b px-3 py-2 text-xs font-semibold bg-muted/50">
              Group Stream Chat & Vault Settings
            </div>
            <div className="flex-1 p-3 overflow-y-auto text-xs space-y-3">
              <div className="rounded border bg-background p-2.5 space-y-2">
                <span className="font-medium">Stream Endpoints (Vault)</span>
                <p className="text-[11px] text-muted-foreground">
                  Configured destinations stored in group secret vault.
                </p>
                <div className="flex items-center justify-between text-[11px] font-mono bg-muted px-2 py-1 rounded">
                  <span>Sovereign HLS (/live/demo)</span>
                  <span className="text-emerald-500">Active</span>
                </div>
              </div>
              <div className="rounded border bg-background p-2.5 space-y-2">
                <span className="font-medium">Matrix Room Channel</span>
                <p className="text-[11px] text-muted-foreground">
                  Linked to Matrix group chat room for live Q&A.
                </p>
                <div className="h-32 border rounded bg-card/50 flex items-center justify-center text-muted-foreground text-[11px]">
                  [Matrix Chat Room Feed]
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
