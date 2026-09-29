/** Capture the live DATA and AGENTS pages while they consume a real Arcade stream. */
import { mkdir, stat, writeFile } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const [baseUrl, runId, lapText = "7", gp = "Lusail", driver = "NOR"] = process.argv.slice(2);
if (!baseUrl || !runId || !/^[\w.-]+$/.test(runId)) {
  throw new Error("Usage: node scripts/trace-live.mjs <base-url> <run-id> [lap] [gp] [driver]");
}

const targetLap = Number(lapText);
const ACTION_LABELS = {
  STAY_OUT: "STAY OUT",
  PIT_NOW: "PIT NOW",
  UNDERCUT: "UNDERCUT",
  OVERCUT: "OVERCUT",
  ALERT: "ALERT",
  DNF: "DNF",
  ERROR: "ERROR",
};
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const reportPath = resolve(repoRoot, "documents/audits", `TRACE_1252_${runId}_browser.json`);
const dataImage = resolve(repoRoot, "documents/audits", `TRACE_1252_${runId}_data.png`);
const agentsImage = resolve(repoRoot, "documents/audits", `TRACE_1252_${runId}_agents.png`);
const latest = { data: {}, agents: {} };
const errors = [];
let browser = null;
let dataPage = null;
let agentsPage = null;
const screenshots = {
  data: { path: dataImage, ok: false, size: 0 },
  agents: { path: agentsImage, ok: false, size: 0 },
};

function observe(page, name) {
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`${name} console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`${name} pageerror: ${error.message}`));
  page.on("response", async (response) => {
    const pathname = new URL(response.url()).pathname;
    if (!pathname.startsWith("/api/")) return;
    const body = await response.json().catch((error) => ({ error: error.message }));
    const routes = latest[name.toLowerCase()];
    if (body !== null || !routes[pathname]) {
      routes[pathname] = { status: response.status(), body };
    }
  });
}

function response(name, route) {
  return latest[name][route]?.body ?? null;
}

function succeeded(name, route) {
  return latest[name][route]?.status === 200;
}

function parseLapTime(text) {
  const parts = text.trim().split(":");
  if (parts.length === 1) return Number(parts[0]);
  if (parts.length === 2) return Number(parts[0]) * 60 + Number(parts[1]);
  return NaN;
}

function matchesSector(text, time, speed) {
  const values = text.match(/\d+(?:\.\d+)?/g)?.map(Number) ?? [];
  let index = 0;
  if (time !== null) {
    if (!Number.isFinite(values[index]) || Math.abs(values[index] - time) > 0.0005) return false;
    index += 1;
  }
  if (speed !== null) {
    if (values[index] !== speed) return false;
    index += 1;
  }
  return values.length === index;
}

function targetTick(tick) {
  const arcade = tick?.arcade ?? {};
  const decision = tick?.strategy?.latest ?? {};
  return (
    arcade.year === 2025 &&
    String(arcade.location ?? "").toLowerCase() === gp.toLowerCase() &&
    String(arcade.driver_main ?? "").toUpperCase() === driver.toUpperCase() &&
    decision.lap_number === targetLap
  );
}

async function visibleTrace() {
  const tick = response("data", "/api/tick");
  const agents = response("agents", "/api/agents");
  const bulk = response("data", "/api/bulk");
  const live = response("data", "/api/live");
  const rendered = await renderedValues();
  const expectedDataLap = `L ${tick?.arcade?.lap}/${tick?.arcade?.total_laps}`;
  const code = driver.toUpperCase();
  const bulkDriver = bulk?.drivers?.[code];
  const liveDriver = live?.drivers?.[code];
  const lastLap = bulkDriver?.laps?.at(-1);
  const racePosition = (tick?.arcade?.race_order?.indexOf(code) ?? -2) + 1;
  const liveSectors = [
    [liveDriver?.s1 ?? null, liveDriver?.v1 ?? null],
    [liveDriver?.s2 ?? null, liveDriver?.v2 ?? null],
    [liveDriver?.s3 ?? null, liveDriver?.vfl ?? null],
  ];
  const lastTimeMatches =
    lastLap?.lap_time === null
      ? rendered.data.row?.last === "—"
      : Number.isFinite(lastLap?.lap_time) &&
        Math.abs(parseLapTime(rendered.data.row?.last ?? "") - lastLap.lap_time) <= 0.0005;
  const expectedTyre = lastLap?.compound
    ? `${lastLap.compound[0]}${lastLap.tyre_life === null ? "" : ` ${Math.round(lastLap.tyre_life)}`}`
    : "—";
  const dataRowMatches =
    rendered.data.row?.driver === code &&
    Number(rendered.data.row.position) === racePosition &&
    rendered.data.row.number === String(bulkDriver?.number ?? "—") &&
    lastLap?.lap === bulkDriver?.laps_revealed &&
    rendered.data.row.stops === String(bulkDriver?.stops ?? "—") &&
    rendered.data.row.tyre === expectedTyre &&
    rendered.data.row.sectors.length === 3 &&
    lastTimeMatches &&
    liveSectors.every(([time, speed], index) =>
      matchesSector(rendered.data.row?.sectors?.[index] ?? "", time, speed),
    );
  return (
    succeeded("data", "/api/tick") &&
    succeeded("data", "/api/bulk") &&
    succeeded("data", "/api/live") &&
    succeeded("agents", "/api/agents") &&
    targetTick(tick) &&
    Number.isInteger(tick?.seq) &&
    tick.seq > 0 &&
    Number.isInteger(agents?.seq) &&
    agents.seq > 0 &&
    tick?.strategy?.start?.no_llm === true &&
    agents?.seq === tick.seq &&
    typeof agents?.orchestrator?.action === "string" &&
    bulk?.available === true &&
    Boolean(bulk?.drivers?.[driver.toUpperCase()]) &&
    Boolean(live?.drivers?.[driver.toUpperCase()]) &&
    rendered.data.lap === expectedDataLap &&
    rendered.data.connection === "Connected" &&
    bulk?.race?.year === tick.arcade.year &&
    bulk?.race?.location === tick.arcade.location &&
    bulkDriver?.laps_revealed === tick.arcade.drivers?.[code]?.laps_completed &&
    liveDriver?.lap === tick.arcade.lap &&
    dataRowMatches &&
    rendered.agents.session === `${gp} · 2025` &&
    rendered.agents.driver === driver &&
    rendered.agents.lap === expectedDataLap &&
    rendered.agents.connection === "Connected" &&
    rendered.agents.action === agents.orchestrator.action &&
    errors.length === 0
  )
    ? { tick, agents, bulk, live, rendered }
    : null;
}

async function renderedValues() {
  if (dataPage === null || agentsPage === null) return null;
  const [data, agents] = await Promise.all([
    dataPage.evaluate((driverCode) => {
      const row = [...document.querySelectorAll("tr.tower-row")].find(
        (candidate) => candidate.querySelector(".col-drv")?.textContent.trim() === driverCode,
      );
      return {
        lap: document.querySelector(".strip-lap")?.innerText.replace(/\s+/g, " ").trim() ?? "",
        connection: document.querySelector(".strip-chip:last-child")?.innerText.trim() ?? "",
        row: row
          ? {
              position: row.querySelector(".col-pos")?.innerText.trim() ?? "",
              number: row.querySelector(".col-num")?.innerText.trim() ?? "",
              driver: row.querySelector(".col-drv")?.innerText.trim() ?? "",
              sectors: [...row.querySelectorAll(".col-sector")].map((cell) =>
                cell.innerText.replace(/\s+/g, " ").trim(),
              ),
              last: row.querySelector(".col-last")?.innerText.trim() ?? "",
              tyre: row.querySelector(".col-tyre")?.innerText.trim() ?? "",
              stops: row.querySelector(".col-stops")?.innerText.trim() ?? "",
            }
          : null,
        text: document.body.innerText,
      };
    }, driver.toUpperCase()),
    agentsPage.evaluate(() => ({
      session: document.querySelector(".header-session")?.innerText.trim() ?? "",
      driver: document.querySelector(".header-driver")?.innerText.trim() ?? "",
      lap:
        document.querySelector(".header-bar .chip:last-child")?.innerText.replace(/\s+/g, " ").trim() ?? "",
      connection: document.querySelector(".header-conn")?.innerText.trim() ?? "",
      action: document.querySelector(".orch-action")?.innerText.trim() ?? "",
      text: document.body.innerText,
    })),
  ]);
  return { data, agents };
}

let status = "fail";
let failure = "";
let rendered = null;
let browserTick = null;
let browserAgents = null;
let dataBulk = null;
let liveLap = null;

try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1486, height: 833 } });
  dataPage = await context.newPage();
  agentsPage = await context.newPage();
  observe(dataPage, "DATA");
  observe(agentsPage, "AGENTS");
  await Promise.all([
    dataPage.goto(`${baseUrl}/data.html`, { waitUntil: "domcontentloaded" }),
    agentsPage.goto(`${baseUrl}/agents.html`, { waitUntil: "domcontentloaded" }),
  ]);
  await Promise.all([
    dataPage.locator(".strip-lap").waitFor({ timeout: 15000 }),
    agentsPage.locator(".orch-action").waitFor({ timeout: 15000 }),
  ]);

  const deadline = Date.now() + 900000;
  let coherent = null;
  while (Date.now() < deadline && coherent === null) {
    coherent = await visibleTrace();
    if (coherent === null) await dataPage.waitForTimeout(250);
  }
  if (coherent === null) throw new Error(`No coherent UI tick for ${gp} ${driver} lap ${targetLap}`);

  browserTick = coherent.tick;
  browserAgents = coherent.agents;
  dataBulk = coherent.bulk;
  liveLap = coherent.live;
  rendered = coherent.rendered;

  const expectedDataLap = `L ${browserTick.arcade.lap}/${browserTick.arcade.total_laps}`;
  const expectedSession = `${gp} · 2025`;
  const sourceAction = String(browserTick.strategy.latest.action ?? "").toUpperCase();
  const expectedAction = ACTION_LABELS[sourceAction] ?? sourceAction;
  if (rendered.data.lap !== expectedDataLap) {
    throw new Error(`DATA DOM lap ${JSON.stringify(rendered.data.lap)} != ${expectedDataLap}`);
  }
  if (rendered.data.connection !== "Connected") {
    throw new Error(`DATA DOM connection is ${JSON.stringify(rendered.data.connection)}`);
  }
  if (rendered.agents.session !== expectedSession || rendered.agents.driver !== driver) {
    throw new Error(`AGENTS DOM identity mismatch: ${JSON.stringify(rendered.agents)}`);
  }
  if (rendered.agents.connection !== "Connected") {
    throw new Error(`AGENTS DOM connection is ${JSON.stringify(rendered.agents.connection)}`);
  }
  if (
    browserAgents.orchestrator.action !== expectedAction ||
    rendered.agents.action !== expectedAction
  ) {
    throw new Error("Wire action, AGENTS API action, and rendered label differ");
  }
  if (errors.length) throw new Error(`Browser errors: ${errors.join(" | ")}`);
} catch (error) {
  failure = `${error.name}: ${error.message}`;
  status = "fail";
  rendered = await renderedValues().catch(() => null);
} finally {
  try {
    await mkdir(dirname(reportPath), { recursive: true });
    if (dataPage !== null && agentsPage !== null) {
      const results = await Promise.allSettled([
        dataPage.screenshot({ path: dataImage, fullPage: true }),
        agentsPage.screenshot({ path: agentsImage, fullPage: true }),
      ]);
      for (const [index, name] of ["data", "agents"].entries()) {
        const result = results[index];
        if (result.status === "rejected") {
          errors.push(`${name} screenshot: ${result.reason.message}`);
          continue;
        }
        const image = await stat(screenshots[name].path);
        screenshots[name].size = image.size;
        screenshots[name].ok = image.size > 0;
        if (!screenshots[name].ok) errors.push(`${name} screenshot is empty`);
      }
    }
  } catch (error) {
    errors.push(`Screenshot capture: ${error.message}`);
  }
  if (browser !== null) {
    await browser.close().catch((error) => errors.push(`Browser close: ${error.message}`));
  }
  if (errors.length) {
    status = "fail";
    failure = [failure, ...errors].filter(Boolean).join(" | ");
  } else if (!failure && rendered !== null && screenshots.data.ok && screenshots.agents.ok) {
    status = "pass";
  }
}

const report = {
  run_id: runId,
  status,
  failure: failure || null,
  target: { gp, driver, decision_lap: targetLap },
  sequences: {
    data_tick: browserTick?.seq ?? null,
    agents_view: browserAgents?.seq ?? null,
    same_seq: browserTick?.seq === browserAgents?.seq,
  },
  host_values: {
    tick: browserTick,
    bulk: dataBulk,
    live_lap: liveLap,
    agents: browserAgents,
  },
  route_statuses: {
    data: Object.fromEntries(Object.entries(latest.data).map(([route, value]) => [route, value.status])),
    agents: Object.fromEntries(Object.entries(latest.agents).map(([route, value]) => [route, value.status])),
  },
  rendered,
  errors,
  screenshots: Object.fromEntries(
    Object.entries(screenshots).map(([name, screenshot]) => [
      name,
      { ...screenshot, path: basename(screenshot.path) },
    ]),
  ),
};
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify({ run_id: runId, status, report: reportPath })}\n`);
process.exitCode = status === "pass" ? 0 : 1;
