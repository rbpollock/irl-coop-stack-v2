// coop-api weather gateway — a free, keyless provider (Open-Meteo) behind a
// cached, provider-agnostic endpoint, so apps never call an external weather
// API directly. Server-to-server auth (the shared KEYCLOAK_GROUPS_TOKEN).
import type { FastifyInstance } from "fastify";
import { getRedis } from "./notifications";

const TOKEN = process.env.KEYCLOAK_GROUPS_TOKEN ?? "";
const OPEN_METEO = "https://api.open-meteo.com/v1/forecast";
const CACHE_TTL_SECONDS = 15 * 60; // 15 min

// WMO weather code -> OpenWeather icon code (day/night chosen by local hour),
// so LiteFarm's existing weather icons keep working unchanged.
function wmoToIcon(code: number, isDay: boolean): string {
  const suffix = isDay ? "d" : "n";
  if (code === 0) return `01${suffix}`; // clear
  if (code === 1) return `02${suffix}`; // mainly clear
  if (code === 2) return `03${suffix}`; // partly cloudy
  if (code === 3) return `04${suffix}`; // overcast
  if (code === 45 || code === 48) return `50${suffix}`; // fog
  if (code >= 51 && code <= 57) return `09${suffix}`; // drizzle
  if (code >= 61 && code <= 67) return `10${suffix}`; // rain
  if (code >= 71 && code <= 77) return `13${suffix}`; // snow
  if (code >= 80 && code <= 82) return `09${suffix}`; // rain showers
  if (code === 85 || code === 86) return `13${suffix}`; // snow showers
  if (code >= 95) return `11${suffix}`; // thunderstorm
  return `03${suffix}`;
}

interface OpenMeteoHourly {
  time: string[];
  temperature_2m: number[];
  relative_humidity_2m: number[];
  precipitation_probability: number[];
  rain: number[];
  snowfall: number[];
  weather_code: number[];
  wind_speed_10m: number[];
}

interface OpenMeteoResponse {
  utc_offset_seconds: number;
  hourly: OpenMeteoHourly;
}

async function fetchOpenMeteo(lat: number, lng: number): Promise<OpenMeteoResponse> {
  const vars =
    "temperature_2m,relative_humidity_2m,precipitation_probability,rain,snowfall,weather_code,wind_speed_10m";
  const url = `${OPEN_METEO}?latitude=${lat}&longitude=${lng}&hourly=${vars}&timezone=auto&forecast_days=5`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`open-meteo ${res.status}`);
  return (await res.json()) as OpenMeteoResponse;
}

export default async function weatherRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get("/api/v1/weather/forecast", async (request, reply) => {
    const auth = request.headers.authorization ?? "";
    if (!TOKEN || auth !== `Bearer ${TOKEN}`) {
      return reply.code(401).send({ error: "unauthorized" });
    }
    const q = request.query as Record<string, string | undefined>;
    const lat = Number(q.lat);
    const lng = Number(q.lng ?? q.lon);
    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lng) ||
      Math.abs(lat) > 90 ||
      Math.abs(lng) > 180
    ) {
      return reply.code(400).send({ error: "valid lat and lng required" });
    }

    // Round to ~1 km so nearby farms share a cached forecast.
    const key = `weather:${lat.toFixed(2)}:${lng.toFixed(2)}`;
    try {
      const cached = await getRedis().get(key);
      if (cached) return JSON.parse(cached);

      const data = await fetchOpenMeteo(lat, lng);
      const h = data.hourly;
      const tzOffset = data.utc_offset_seconds;
      const slots: Record<string, number | string>[] = [];
      // Hourly from the provider; sample every 3 hours (matches the old 5-day/3-hour).
      for (let i = 0; i < h.time.length; i += 3) {
        const dt = Math.round(new Date(h.time[i]).getTime() / 1000);
        const localHour = ((dt + tzOffset) % 86400) / 3600;
        const isDay = localHour >= 6 && localHour < 18;
        slots.push({
          dt,
          tempC: Math.round(h.temperature_2m[i] * 10) / 10,
          iconCode: wmoToIcon(h.weather_code[i], isDay),
          pop: h.precipitation_probability[i] ?? 0,
          rainMm3h: h.rain[i] ?? 0,
          snowMm3h: h.snowfall[i] ?? 0,
          windMs: Math.round(h.wind_speed_10m[i] * 10) / 10,
          humidity: h.relative_humidity_2m[i] ?? 0,
        });
      }

      const result = {
        city: { name: "", timezoneOffsetSeconds: tzOffset },
        slots,
      };
      await getRedis().set(key, JSON.stringify(result), "EX", CACHE_TTL_SECONDS);
      return result;
    } catch (err) {
      request.log.error({ err }, "weather lookup failed");
      return reply.code(502).send({ error: "weather provider failed" });
    }
  });
}
