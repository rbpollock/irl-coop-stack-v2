import { exec, execFile } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import * as yaml from "js-yaml";
import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";

// --- Stack status: declared-vs-running reconciler.
// Declared state = the generated tree (infra/out/dev/compose/<pillar>/) plus
// the compose of every `type: source` app (spec `source:` path). Running
// state = `docker ps -a`. Match on the compose project+service labels docker
// stamps on every container. Everything running-but-not-declared is drift
// (orphans); everything declared-but-not-running is a gap (missing).

const STACK_ROOT = process.env.STACK_ROOT ?? path.resolve(__dirname, "../../..");
const COMPOSE_DIR = path.join(STACK_ROOT, "infra/out/dev/compose");
const APPS_DIR = path.join(STACK_ROOT, "infra/instances/dev/apps");

type ServiceDecl = { service: string; image?: string; healthcheck?: boolean };
type DeclaredCompose = {
  id: string;
  kind: "tree" | "source";
  pillar: string;
  composePath: string;
  services: ServiceDecl[];
};

type ContainerInfo = {
  name: string;
  image: string;
  state: string;
  status: string;
  health: string | null;
  ports: string;
  project: string;
  service: string;
  configFiles: string[];
  command: string;
};

function loadYaml(p: string): any {
  try {
    return yaml.load(fs.readFileSync(p, "utf8"));
  } catch {
    return null;
  }
}

/** Service names (+ image/healthcheck presence) from a compose file, with the
 *  matching .override.yml merged on top (service-level dict merge). */
function composeServices(basePath: string): ServiceDecl[] {
  const base = loadYaml(basePath);
  const overridePath = basePath.replace(/\.yml$/, ".override.yml");
  const override = fs.existsSync(overridePath) ? loadYaml(overridePath) : null;
  const names = new Set<string>([
    ...Object.keys(base?.services ?? {}),
    ...Object.keys(override?.services ?? {}),
  ]);
  const out: ServiceDecl[] = [];
  for (const name of names) {
    const b = base?.services?.[name] ?? {};
    const o = override?.services?.[name] ?? {};
    out.push({
      service: name,
      image: (o.image as string) ?? (b.image as string),
      healthcheck: Boolean(o.healthcheck ?? b.healthcheck),
    });
  }
  return out.sort((a, b) => a.service.localeCompare(b.service));
}

/** Every compose file the tree declares: one per pillar + one per source app. */
function declaredComposes(): DeclaredCompose[] {
  const out: DeclaredCompose[] = [];
  if (fs.existsSync(COMPOSE_DIR)) {
    for (const pillar of fs.readdirSync(COMPOSE_DIR).sort()) {
      const base = path.join(COMPOSE_DIR, pillar, "docker-compose.yml");
      if (!fs.existsSync(base)) continue;
      out.push({
        id: `tree:${pillar}`,
        kind: "tree",
        pillar,
        composePath: base,
        services: composeServices(base),
      });
    }
  }
  if (fs.existsSync(APPS_DIR)) {
    for (const f of fs.readdirSync(APPS_DIR).sort()) {
      const spec = loadYaml(path.join(APPS_DIR, f));
      if (!spec || spec.type !== "source" || !spec.source) continue;
      const srcDir = path.resolve(STACK_ROOT, spec.source);
      const base = path.join(srcDir, "docker-compose.yml");
      if (!fs.existsSync(base)) continue;
      out.push({
        id: `source:${spec.name}`,
        kind: "source",
        pillar: (spec.pillar as string) ?? "source",
        composePath: base,
        services: composeServices(base),
      });
    }
  }
  return out;
}

/** docker ps --format '{{json .}}' emits Labels either as a JSON object or
 *  as a flattened "k=v,k=v" string, plus the literal "<no value>" for
 *  containers created outside compose. */
function parseLabels(raw: unknown): Record<string, string> {
  if (raw && typeof raw === "object") return raw as Record<string, string>;
  if (typeof raw !== "string" || raw === "<no value>") return {};
  const out: Record<string, string> = {};
  for (const part of raw.split(",")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i)] = part.slice(i + 1);
  }
  return out;
}

function dockerContainers(): Promise<ContainerInfo[]> {
  return new Promise((resolve, reject) => {
    execFile(
      "docker",
      ["ps", "-a", "--format", "{{json .}}"],
      { timeout: 10_000, maxBuffer: 8 * 1024 * 1024 },
      (err, stdout) => {
        if (err) return reject(err);
        const list: ContainerInfo[] = [];
        for (const line of stdout.split("\n")) {
          if (!line.trim()) continue;
          try {
            const j = JSON.parse(line);
            const labels = parseLabels(j.Labels);
            list.push({
              name: String(j.Names ?? "").replace(/^\//, ""),
              image: String(j.Image ?? ""),
              state: String(j.State ?? ""),
              status: String(j.Status ?? ""),
              health: (String(j.Status ?? "").match(/\(([a-z]+)\)/) ?? [])[1] ?? null,
              ports: String(j.Ports ?? ""),
              project: String(labels["com.docker.compose.project"] ?? ""),
              service: String(labels["com.docker.compose.service"] ?? ""),
              configFiles: String(labels["com.docker.compose.project.config_files"] ?? "")
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
              command: String(j.Command ?? ""),
            });
          } catch {
            /* skip malformed line */
          }
        }
        resolve(list);
      }
    );
  });
}

export default async function statusRoutes(fastify: FastifyInstance): Promise<void> {
  // Declared-vs-running stack status, auth-gated like every coop-api route.
  fastify.get("/api/v1/stack/status", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    let containers: ContainerInfo[];
    try {
      containers = await dockerContainers();
    } catch (err) {
      request.log.error({ err }, "docker ps failed");
      return reply.code(503).send({ error: "docker_unavailable" });
    }

    const decls = declaredComposes();
    const matchedNames = new Set<string>();
    const pillars: any[] = [];

    for (const decl of decls) {
      const project = path.basename(path.dirname(decl.composePath));
      const services = decl.services.map((svc) => {
        const c = containers.find((x) => x.project === project && x.service === svc.service);
        if (c) matchedNames.add(c.name);
        return {
          service: svc.service,
          declared_healthcheck: svc.healthcheck,
          image: svc.image ?? null,
          container: c
            ? {
                name: c.name,
                state: c.state,
                health: c.health,
                status: c.status,
                image: c.image,
                ports: c.ports,
              }
            : null,
        };
      });
      const up = services.filter((s: any) => s.container?.state === "running").length;
      const missing = services
        .filter((s: any) => !s.container)
        .map((s: any) => s.service);
      pillars.push({
        id: decl.id,
        pillar: decl.pillar,
        kind: decl.kind,
        compose: decl.composePath,
        declared: services.length,
        up,
        down: services.length - up,
        missing,
        services,
      });
    }

    const orphans = containers
      .filter((c) => !matchedNames.has(c.name))
      .map((c) => ({
        name: c.name,
        image: c.image,
        state: c.state,
        status: c.status,
        project: c.project,
        compose: c.configFiles[0] ?? null,
      }))
      .sort((a, b) => a.name.localeCompare(b.name));

    const totalDeclared = pillars.reduce((n, p) => n + p.declared, 0);
    const totalUp = pillars.reduce((n, p) => n + p.up, 0);
    const healthy = containers.filter((c) => c.health === "healthy").length;

    // Ephemeral browser-runner instances (the fleet's execution units).
    const runners = containers
      .filter((c) => c.image.includes("browser-runner"))
      .map((c) => ({
        name: c.name,
        state: c.state,
        status: c.status,
        scenario: (() => {
          const m = c.command.match(/run\.js\s+([a-z0-9-]+)/) 
            || c.command.match(/e2e\/([a-z0-9-]+)/) 
            || c.command.match(/["']?([a-z0-9-]+-flow)["']?/i);
          return m ? m[1] : null;
        })(),
      }))
      .sort((a, b) => a.name.localeCompare(b.name));

    return reply.send({
      generated_at: new Date().toISOString(),
      stack_root: STACK_ROOT,
      summary: {
        declared: totalDeclared,
        containers: containers.length,
        up: totalUp,
        down: totalDeclared - totalUp,
        healthy,
        orphans: orphans.length,
      },
      browser_runners: {
        active: runners.filter((r) => r.state === "running").length,
        total: runners.length,
        instances: runners,
      },
      pillars,
      orphans,
    });
  });

  // Trigger a browser runner execution
  fastify.post("/api/v1/stack/browser/run", async (request, reply) => {
    const session = verifyBearer(request, reply);
    if (!session) return;
    
    const body = (request.body ?? {}) as { scenario?: string };
    const scenario = body.scenario ?? "files-flow";
    if (!["files-flow", "linking-flow"].includes(scenario)) {
      return reply.code(400).send({ error: "invalid_request", error_description: "Unknown scenario" });
    }

    const containerName = `browser-runner-${scenario}-${Date.now()}`;
    const e2eUser = "e2e-test@irl.coop";
    const e2ePassword = process.env.E2E_PASSWORD ?? "";

    // Launch the docker container in background (non-blocking)
    const cmd = `docker run -d --rm --name "${containerName}" ` +
                `-v /tmp:/tmp ` +
                `-e "E2E_USER=${e2eUser}" ` +
                `-e "E2E_PASSWORD=${e2ePassword}" ` +
                `irlcoop/browser-runner node /app/runner/run.js ${scenario}`;

    exec(cmd, (err, stdout, stderr) => {
      if (err) {
        request.log.error({ err: err.message, stderr }, "Failed to start browser-runner container");
      } else {
        request.log.info({ containerName, stdout: stdout.trim() }, "Started browser-runner container in background");
      }
    });

    return reply.send({ success: true, container: containerName, scenario });
  });
}
