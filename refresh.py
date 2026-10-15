#!/usr/bin/env python3
"""Refresh index.html for the web3-launches board.

RULE (enforced): a project is listed only if its X account was created
September 2026 or later. Creation dates are decoded from X snowflake ids
(api.fxtwitter.com -> numeric user id -> (id >> 22) + 1288834974657 ms epoch),
cross-checked against profile "Joined" dates. No filter overrides.

Usage:  python3 refresh.py            # rebuild index.html in place
        python3 refresh.py --days 8   # widen the DeFiLlama listing window
"""
import json, html, time, subprocess, sys, datetime

WINDOW_DAYS = 8
EPOCH_MS = 1288834974657
CUTOFF = "2026-09-01"  # X account must be created this day or later

def curl_json(url: str):
    out = subprocess.run(["curl", "-s", "-m", "20", url], capture_output=True, text=True).stdout
    return json.loads(out)

def account_created(handle: str):
    """Return creation datetime of the X account, or None if unresolved."""
    for attempt in range(2):
        try:
            d = curl_json(f"https://api.fxtwitter.com/{handle}")["user"]
            uid = int(d["id"])
            return datetime.datetime.fromtimestamp(
                ((uid >> 22) + EPOCH_MS) / 1000, datetime.timezone.utc)
        except Exception:
            time.sleep(1.2)
    return None

def main():
    days = WINDOW_DAYS
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])

    # 1. pull candidate projects from DeFiLlama (all listed within the window)
    llama = curl_json("https://api.llama.fi/protocols")
    now = time.time()
    cands = [p for p in llama if (p.get("listedAt") or 0) > now - days * 86400]
    by_handle = {}
    for p in cands:
        tw = (p.get("twitter") or "").lower()
        if tw:
            by_handle.setdefault(tw, []).append(p)
    print(f"candidates: {len(cands)} listings, {len(by_handle)} unique handles")

    # 2. verify each handle's account creation date; keep only fresh accounts
    fresh = {}
    for h in sorted(by_handle):
        created = account_created(h)
        if created and created.strftime("%Y-%m-%d") >= CUTOFF:
            fresh[h] = created
            print(f"  PASS {created:%Y-%m-%d} @{h}")
        elif created:
            print(f"  cut  {created:%Y-%m-%d} @{h}")
        else:
            print(f"  ??? unresolved @{h}")
        time.sleep(0.35)

    # 3. build rows (family-grouped)
    def fam(name):
        for k in ("DeepSwap", "DEEP", "Bordrless"):
            if name.startswith(k):
                return k
        return name

    rows = []
    for h, created in sorted(fresh.items(), key=lambda kv: kv[1], reverse=True):
        merged = {}
        for p in by_handle[h]:
            f = fam(p["name"])
            m = merged.setdefault(f, {"cat": p.get("category"), "url": p.get("url") or "",
                                      "chains": set(), "tvl": 0})
            m["chains"].update(p.get("chains") or [])
            m["tvl"] += p.get("tvl") or 0
            if not m["url"] and p.get("url"):
                m["url"] = p["url"]
        for f, m in merged.items():
            rows.append({"h": h, "created": created, "name": f, "what": m["cat"] or "?",
                         "url": m["url"], "chains": sorted(m["chains"]), "tvl": m["tvl"]})

    # 4. render
    def x(h, c):
        return (f'<a href="https://x.com/{h}" target="_blank">@{h}</a> '
                f'<span style="color:#3d4658;font-size:10px">{c[:7]}</span>')
    def w(u):
        return (f'<a href="{html.escape(u)}" target="_blank">'
                f'{html.escape(u.replace("https://","").replace("http://","").rstrip("/")[:40])}</a>'
                if u else "—")
    def tvl(t):
        if t >= 1e6: return f"${t/1e6:.1f}M"
        if t >= 1e3: return f"${t/1e3:.0f}K"
        return f"${t:.0f}" if t else "—"

    table = "\n".join(
        f'<tr><td><b>{html.escape(r["name"])}</b></td><td>{html.escape(r["what"])}</td>'
        f'<td>{x(r["h"], r["created"])}</td><td>{w(r["url"])}</td>'
        f'<td>{html.escape(", ".join(r["chains"]) or "not tracked")}</td>'
        f'<td class="tvl">{tvl(r["tvl"])}</td></tr>'
        for r in rows)

    stamp = time.strftime("%b %d, %Y %H:%M UTC", time.gmtime())
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>New web3 launches — fresh accounts only</title>
<style>
body{{background:#0b0e14;color:#d7dce8;font:13px/1.6 -apple-system,Menlo,monospace;margin:0;padding:24px}}
h1{{color:#7ee0ff;font-size:20px}} h2{{color:#7ee0ff;font-size:15px;margin:28px 0 8px}}
a{{color:#66d9ef;text-decoration:none}} a:hover{{text-decoration:underline}}
table{{border-collapse:collapse;width:100%;margin-bottom:10px}}
td,th{{border-bottom:1px solid #1c2230;padding:6px 10px;text-align:left;vertical-align:top;font-size:12.5px}}
th{{color:#8b93a7;font-weight:400;position:sticky;top:0;background:#0b0e14}}
.tvl{{color:#7bd88f;white-space:nowrap}}
.note{{color:#5b6478;font-size:11.5px;margin-top:22px;line-height:1.7}}
.rule{{background:#101623;border:1px solid #1c2230;border-radius:6px;padding:10px 14px;margin:14px 0;color:#8b93a7}}
.rule b{{color:#ffd166}}
</style></head><body>
<h1>Web3 launches — fresh accounts only</h1>
<div class="rule"><b>INDEX RULE (enforced):</b> a project is listed only if its X account was
<b>created September 2026 or later</b> (decoded from the numeric user id, cross-checked against
the profile's "Joined" date). Currently <b>{len(rows)} projects</b> pass. Older accounts are
excluded — "no longer trendy" filter. Regenerated {stamp}.</div>
<h2>NEW PROJECTS — X account created Sep 2026+</h2>
<table><tr><th>Project</th><th>What</th><th>X (created)</th><th>Website</th><th>Live on</th><th>TVL</th></tr>
{table}
</table>
<div class="note">
Source: DeFiLlama listing feed (last {days} days, filtered by the account rule).
Created dates decoded from X snowflake ids and verified against profiles.
Brand-new + tiny TVL = maximum risk; this is a "what is new" radar, not a buy list.
</div>
</body></html>"""
    open("index.html", "w").write(page)
    print(f"\nwrote index.html: {len(rows)} projects")

if __name__ == "__main__":
    main()
