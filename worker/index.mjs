const workflow = "https://api.github.com/repos/dustinbowers51/pocket-politics-records/actions/workflows/live-records.yml";
const hour = 3600000;

export default {
  fetch(request, env) {
    return env.ASSETS.fetch(request);
  },

  async scheduled(event, env) {
    if (!env.GITHUB_ACTIONS_TOKEN) return;
    const slot = Math.floor(event.scheduledTime / hour) * hour;
    const manifest = await env.ASSETS.fetch(new Request("https://records.invalid/manifest.json"));
    if (!manifest.ok) throw new Error("Cannot read deployed manifest");
    const updated = Date.parse((await manifest.json()).updatedAt);
    if (!Number.isFinite(updated)) throw new Error("Invalid manifest timestamp");
    if (updated >= slot) return;

    const headers = {
      Authorization: "Bearer " + env.GITHUB_ACTIONS_TOKEN,
      Accept: "application/vnd.github+json",
      "User-Agent": "pocket-politics-records-cron",
      "Content-Type": "application/json",
    };
    const runs = await fetch(workflow + "/runs?branch=main&per_page=20", { headers });
    if (!runs.ok) throw new Error("Workflow status HTTP " + runs.status);
    if ((await runs.json()).workflow_runs.some(run => run.status !== "completed")) return;
    const response = await fetch(workflow + "/dispatches", {
      method: "POST", headers,
      body: JSON.stringify({ ref: "main", inputs: { backup_slot: String(slot) } }),
    });
    if (!response.ok) throw new Error("Backup dispatch HTTP " + response.status);
  },
};
