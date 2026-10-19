// CoZjem promotion alerts (Supabase Edge Function "push").
// POST {action:"sub", sub, lang, stores, keys}   save a browser push subscription (from cozjem.com only)
// POST {action:"unsub", endpoint}                remove it
// POST {action:"send"}                           notify subscribers about promotions that are new since the last send.
//   "send" is safe to call by anyone: it only sends when promos.json has new items and at most once every 6 hours (the workflow runs daily).
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import webpush from "npm:web-push@3.6.7";

const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
const SRC = "https://raw.githubusercontent.com/Afeez-Ola/cozjem/main/promos.json";
const STORES = ["Lidl", "Biedronka", "Aldi", "Auchan"];
const OK_ORIGIN = /^(https:\/\/(www\.)?cozjem\.com|http:\/\/localhost(:\d+)?)$/;
const MIN_GAP_H = 6;
const cors = (o: string | null) => ({
  "Access-Control-Allow-Origin": o && OK_ORIGIN.test(o) ? o : "https://cozjem.com",
  "Access-Control-Allow-Headers": "content-type, authorization, apikey, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Vary": "Origin",
});
const json = (o: string | null, body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors(o), "Content-Type": "application/json" } });

type Item = { t: string; p?: number | null; pct?: number | null; hl?: string; k?: string | null; until: number; store: string };

async function getState(id: string) {
  const { data } = await sb.from("push_state").select("val").eq("id", id).maybeSingle();
  return data?.val ?? null;
}
const setState = (id: string, val: unknown) => sb.from("push_state").upsert({ id, val, updated_at: new Date().toISOString() });

const plN = (n: number, one: string, few: string, many: string) => {
  if (n === 1) return one;
  const d = n % 10, h = n % 100;
  return d >= 2 && d <= 4 && (h < 12 || h > 14) ? few : many;
};
const zl = (n: number) => n.toFixed(2).replace(".", ",") + " zł";
const short = (t: string) => t.replace(/\s+/g, " ").split(" ").slice(0, 4).join(" ");
const tag = (x: Item) => (x.pct ? `−${x.pct}%` : x.hl ? x.hl : x.p ? zl(x.p) : "");

function message(lang: string, fresh: Item[], mine: Item[]) {
  const pick = (mine.length ? mine : fresh).slice().sort((a, b) => (b.pct || 0) - (a.pct || 0)).slice(0, 3);
  const lines = pick.map((x) => `${short(x.t)} ${tag(x)} (${x.store})`).join(" · ");
  const stores = [...new Set(fresh.map((x) => x.store))].join(", ");
  if (lang === "en") {
    const title = mine.length
      ? `${mine.length} new deal${mine.length === 1 ? "" : "s"} on things you cook`
      : `${fresh.length} new promotion${fresh.length === 1 ? "" : "s"} at ${stores}`;
    return { title, body: lines };
  }
  const title = mine.length
    ? `${mine.length} ${plN(mine.length, "nowa promocja", "nowe promocje", "nowych promocji")} na Twoje składniki`
    : `${fresh.length} ${plN(fresh.length, "nowa promocja", "nowe promocje", "nowych promocji")}: ${stores}`;
  return { title, body: lines };
}

async function send(force: boolean) {
  const last = await getState("last");
  if (!force && last?.at && Date.now() - Date.parse(last.at) < MIN_GAP_H * 3600e3) return { skipped: "too soon" };
  const r = await fetch(SRC + "?t=" + Date.now(), { headers: { "Cache-Control": "no-cache" } });
  if (!r.ok) return { error: "promos.json " + r.status };
  const d = await r.json();
  const now = Date.now();
  const items: Item[] = [];
  for (const [store, o] of Object.entries<any>(d.stores || {})) {
    if (!STORES.includes(store)) continue;
    for (const x of o.items || []) if (x && typeof x.t === "string" && x.until >= now) items.push({ ...x, store });
  }
  const id = (x: Item) => `${x.store}|${x.t}|${x.p ?? ""}`;
  const seen = new Set<string>((await getState("seen"))?.ids || []);
  const fresh = items.filter((x) => !seen.has(id(x)));
  await setState("seen", { ids: items.map(id) });
  if (!fresh.length) return { fresh: 0 };

  const v = await getState("vapid");
  if (!v?.privateKey) return { error: "no keys yet" };
  webpush.setVapidDetails("mailto:hello@cozjem.com", v.publicKey, v.privateKey);
  let sent = 0, gone = 0, from = 0;
  while (true) {
    const { data: subs } = await sb.from("push_subs").select("endpoint,sub,lang,stores,keys").range(from, from + 499);
    if (!subs?.length) break;
    for (let i = 0; i < subs.length; i += 50) {
      await Promise.allSettled(subs.slice(i, i + 50).map(async (s: any) => {
        const f = s.stores?.length ? fresh.filter((x) => s.stores.includes(x.store)) : fresh;
        if (!f.length) return;
        const keys = new Set<string>(s.keys || []);
        const mine = f.filter((x) => x.k && keys.has(x.k));
        const m = message(s.lang, f, mine);
        try {
          await webpush.sendNotification(s.sub, JSON.stringify({ ...m, url: "/#offers", tag: "cozjem-promos" }), { TTL: 12 * 3600, urgency: "normal" });
          sent++;
        } catch (e: any) {
          if (e?.statusCode === 404 || e?.statusCode === 410) { gone++; await sb.from("push_subs").delete().eq("endpoint", s.endpoint); }
        }
      }));
    }
    if (subs.length < 500) break;
    from += 500;
  }
  await setState("last", { at: new Date().toISOString(), fresh: fresh.length, sent, gone });
  return { fresh: fresh.length, sent, gone };
}

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
  if (req.method === "GET") {
    let v = await getState("vapid");
    if (!v?.publicKey) { // first use: create the key pair on the server, so the private key never leaves it
      const k = webpush.generateVAPIDKeys();
      await sb.from("push_state").insert({ id: "vapid", val: k });
      v = await getState("vapid");
    }
    return new Response(JSON.stringify({ publicKey: v.publicKey }), {
      headers: { ...cors(origin), "Content-Type": "application/json", "Cache-Control": "public, max-age=86400" },
    });
  }
  if (req.method !== "POST") return json(origin, { error: "method" }, 405);
  let b: any;
  try { b = await req.json(); } catch { return json(origin, { error: "bad json" }, 400); }

  if (b.action === "send") return json(origin, await send(false));

  if (!origin || !OK_ORIGIN.test(origin)) return json(origin, { error: "origin" }, 403);
  if (b.action === "sub") {
    const s = b.sub;
    if (!s || typeof s.endpoint !== "string" || !/^https:\/\//.test(s.endpoint) || s.endpoint.length > 1000 ||
        typeof s.keys?.p256dh !== "string" || typeof s.keys?.auth !== "string" || s.keys.p256dh.length > 200 || s.keys.auth.length > 100)
      return json(origin, { error: "bad subscription" }, 400);
    const lang = b.lang === "en" ? "en" : "pl";
    const stores = Array.isArray(b.stores) ? b.stores.filter((x: unknown) => STORES.includes(x as string)) : [];
    const keys = Array.isArray(b.keys) ? b.keys.filter((x: unknown) => typeof x === "string" && /^[a-z_]{1,24}$/.test(x)).slice(0, 300) : [];
    const { error } = await sb.from("push_subs").upsert({
      endpoint: s.endpoint, sub: { endpoint: s.endpoint, keys: { p256dh: s.keys.p256dh, auth: s.keys.auth } },
      lang, stores, keys, updated_at: new Date().toISOString(),
    });
    return error ? json(origin, { error: "save failed" }, 500) : json(origin, { ok: true });
  }
  if (b.action === "unsub") {
    if (typeof b.endpoint !== "string") return json(origin, { error: "endpoint" }, 400);
    await sb.from("push_subs").delete().eq("endpoint", b.endpoint);
    return json(origin, { ok: true });
  }
  return json(origin, { error: "action" }, 400);
});
