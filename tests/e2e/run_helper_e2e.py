"""End-to-end check of the Ky helper page in a real browser.

Loads helper/ky.html with stand-ins for Claude's runtime (Indeed connector,
Claude sampling, downloads; no database, so the page uses browser storage),
then walks the whole flow: paste a resume, ZIP, search, tailored resumes,
fact check, resume designs, PDF/Word downloads, Ask Ky chat with a tool call,
hours log and CSV.

Needs: pip install playwright, a Chrome/Chromium, and the browser libraries
unpacked locally (see LIBS below) because the test browser may not reach the CDN.

    python tests/e2e/run_helper_e2e.py --libs /path/to/unpacked/npm/packages [--shots out_dir]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures"

CDN = {
    "https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js": "jspdf-2.5.1/package/dist/jspdf.umd.min.js",
    "https://cdn.jsdelivr.net/npm/docx@8.5.0/build/index.umd.js": "docx-8.5.0/package/build/index.umd.js",
    "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.min.js": "pdfjs-dist-3.11.174/package/build/pdf.min.js",
    "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js": "pdfjs-dist-3.11.174/package/build/pdf.worker.min.js",
    "https://cdn.jsdelivr.net/npm/mammoth@1.6.0/mammoth.browser.min.js": "mammoth-1.6.0/package/mammoth.browser.min.js",
}

RESUME = """Maya Torres
Riverside, CA | (555) 010-2345 | maya.torres@example.com

EXPERIENCE
Caregiver, Sunrise Home Care, Riverside, CA (Mar 2025 - Present)
- Assisted elderly clients with bathing, dressing and toileting
- Took and recorded blood pressure, pulse and temperature each visit
- Helped clients walk and transfer from bed to wheelchair safely
- Cared for 4 clients per week

Cashier, Valley Market (Jun 2023 - Feb 2025)
- Handled 150+ customer transactions per shift

EDUCATION
Riverside City College - Pre-Nursing, in progress, GPA 3.6

CERTIFICATIONS
BLS for Healthcare Providers, American Heart Association, expires 2028-02

LANGUAGES: English, Spanish
"""

PROFILE = {
    "name": "Maya Torres", "location": "Riverside, CA",
    "contact": {"email": "maya.torres@example.com", "phone": "(555) 010-2345"}, "goal": "",
    "certifications": [{"name": "BLS", "full_name": "BLS for Healthcare Providers", "issuer": "American Heart Association", "earned": "", "expires": "2028-02"}],
    "experience": [
        {"title": "Caregiver", "employer": "Sunrise Home Care", "location": "Riverside, CA", "start": "2025-03", "end": "present", "patient_care": True,
         "duties": ["Assisted elderly clients with bathing, dressing and toileting", "Took and recorded blood pressure, pulse and temperature each visit",
                    "Helped clients walk and transfer from bed to wheelchair safely"], "numbers": ["4 clients per week"]},
        {"title": "Cashier", "employer": "Valley Market", "location": "", "start": "2023-06", "end": "2025-02", "patient_care": False,
         "duties": ["Handled 150+ customer transactions per shift"], "numbers": ["150+"]},
    ],
    "education": [{"school": "Riverside City College", "program": "Pre-Nursing", "status": "in progress", "start": "", "end": "", "gpa": "3.6", "prerequisites_done": []}],
    "volunteer": [], "skills": {"clinical": ["Vital signs"], "technical": [], "soft": [], "languages": ["English", "Spanish"]},
}

TAILORED = {
    "target_title": "Certified Nursing Assistant | BLS Certified",  # she has no CNA: the headline must be dropped
    "summary": "Pre-nursing student with hands-on home care experience assisting clients with activities of daily living and vital signs.",
    "certifications": ["BLS for Healthcare Providers", "CNA"],  # CNA is invented: the fact check must remove it
    "experience": [
        {"title": "Caregiver", "employer": "Sunrise Home Care", "location": "Riverside, CA", "start": "2025-03", "end": "present",
         "bullets": ["Assisted 4 clients per week with activities of daily living (ADLs), including bathing and dressing",
                     "Measured and documented vital signs including blood pressure, pulse and temperature",
                     "Supported safe patient transfers and mobility from bed to wheelchair",
                     "Charted care for 25 patients per shift in Epic"]},  # invented: must be removed
        {"title": "Cashier", "employer": "Valley Market", "location": "", "start": "2023-06", "end": "2025-02",
         "bullets": ["Delivered fast, friendly customer service for 150+ customers per shift"]},
    ],
    "education": [{"school": "Riverside City College", "program": "Pre-Nursing", "status": "in progress", "end": "", "gpa": "3.6", "details": ""}],
    "skills": {"clinical": ["Vital signs", "Activities of daily living (ADLs)", "Patient transfers"], "technical": [], "languages": "English, Spanish"},  # a string, not a list
    "volunteer": [],
    "cover_letter": "P1 about the hospital.\n\nP2 with two examples.\n\nP3 about nursing.",  # one string, not a list
    "keywords_used": ["vital signs"], "questions_for_candidate": ["About how many hours a week do you work?"],
    "why_this_job": "Great hands-on role for nursing school.", "interview_tips": ["Talk about safe transfers."],
}

STUB = r"""
(() => {
  const FIX = %(fix)s;
  // A small stand-in for the artifact database (Firestore-like), used with --db.
  // Claude's real runtime hands the page read-only data; the stand-ins do the same.
  const deepFreeze = (x) => { if (x && typeof x === "object" && !Object.isFrozen(x)) { Object.freeze(x); Object.values(x).forEach(deepFreeze); } return x; };
  function makeDb() {
    const docs = new Map(), subs = [];
    const clone = (x) => JSON.parse(JSON.stringify(x));
    const collOf = (path) => path.split("/").slice(0, -1).join("/");
    const notify = () => setTimeout(() => subs.slice().forEach((s) => s.fire()), 5);
    const snapDoc = (path) => { const d = docs.get(path); return { id: path.split("/").pop(), exists: !!d, data: () => (d ? deepFreeze(clone(d)) : undefined), metadata: { fromCache: false, hasPendingWrites: false } }; };
    const docRef = (path) => ({
      id: path.split("/").pop(), path,
      async get() { return snapDoc(path); },
      async set(data) { docs.set(path, clone(data)); notify(); },
      async update(data) { if (!docs.has(path)) throw { code: "invalid_argument" }; docs.set(path, { ...docs.get(path), ...clone(data) }); notify(); },
      async delete() { docs.delete(path); notify(); },
      onSnapshot(next) { const s = { fire: () => next(snapDoc(path)) }; subs.push(s); setTimeout(s.fire, 30); return () => subs.splice(subs.indexOf(s), 1); },
    });
    const collRef = (path) => ({
      path, doc: (id) => docRef(path + "/" + id),
      onSnapshot(next) {
        const s = { fire: () => { const ds = [...docs.keys()].filter((k) => collOf(k) === path).sort().map(snapDoc); next({ docs: ds, size: ds.length, empty: !ds.length, docChanges: () => [], metadata: { fromCache: false, hasPendingWrites: false } }); } };
        subs.push(s); setTimeout(s.fire, 300); return () => subs.splice(subs.indexOf(s), 1);
      },
    });
    if (window.__SEED) for (const [k, v] of Object.entries(window.__SEED)) docs.set(k, clone(v));  // replay saved data
    window.__db = docs; window.__dbSet = (path, data) => { docs.set(path, clone(data)); notify(); };
    return { doc: docRef, collection: collRef };
  }
  const db = %(usedb)s ? makeDb() : null;
  window.__jobs = () => (window.__db ? [...window.__db].filter(([k]) => k.startsWith("jobs/")).map(([k, v]) => ({ ...v, key: k.slice(5) })) : JSON.parse(localStorage.getItem("ky.jobs")));
  window.__settings = () => (window.__db ? window.__db.get("settings/main") : JSON.parse(localStorage.getItem("ky.settings")));
  window.__saved = []; window.__sampleCalls = 0;
  // ZipRecruiter answers with JSON (a shape the page has to find on its own); with --db it's connected,
  // without it it isn't, so both paths get exercised.
  // Same shape as the live ZipRecruiter connector (checked against a real call); values are made up.
  const ZIP_JOBS = { request: {}, results: [
      { listing_key: "zr-1", title: "Patient Care Assistant", company: "Example Medical Center", location: "Riverside, California", is_remote: false,
        salary: { min_annual: 41600, max_annual: 49920 }, job_redirect_url: "https://example.com/zr/1", job_type: "Part-time · On-site", benefits: "Medical, Dental", days_ago: 3 },
      { listing_key: "zr-2", title: "Veterinary Technician ICU", company: "Example Animal Hospital", location: "Riverside, California", is_remote: false,
        salary: { min_annual: 38500, max_annual: 54000 }, job_redirect_url: "https://example.com/zr/2", job_type: "Full-time · On-site", benefits: null, days_ago: 1 }],
    status: "OK", meta: { count: 2, limit: 5, total: 2 }, search_url: "https://example.com/search", warnings: [], conversation_id: "c1" };
  window.__zipArgs = []; window.__ZIP_JOBS = ZIP_JOBS; window.__kyTest = true;
  const mcp = {
    async describeTool(server, tool) {
      if (server === "ZipRecruiter") return { name: "search_jobs", description: "", inputSchema: { type: "object", properties: { conversation_id: { type: "string" }, country_admin_code: { type: "string" }, job_role: { type: "string" }, location: { type: "string" }, radius_miles: { type: "number" } } } };
      throw { code: "bad_request" };
    },
    async callTool(server, tool, input) {
      if (server === "ZipRecruiter") {
        if (!%(usedb)s) throw { code: "server_not_connected", message: "not connected" };
        window.__zipArgs.push(input);
        return { content: [{ type: "text", text: JSON.stringify(ZIP_JOBS) }], payload: ZIP_JOBS };
      }
      if (tool === "search_jobs") return { content: [], payload: { result: FIX.search } };
      if (tool === "get_job_details") return { content: [], payload: { result: FIX.details[input.job_id] || FIX.details.default } };
      throw { code: "tool_error", message: "unknown" };
    },
  };
  async function sample(input, opts = {}) {
    window.__sampleCalls++;
    let text = "Great question! **Patient-care experience** is hands-on work with patients, like taking vital signs or helping with bathing and meals.\n- Log every shift\n- Keep your supervisor's contact\n- Check each school's admissions page";
    const last = Array.isArray(input) ? input[input.length - 1].content : String(input);
    if (opts.tools && /worked/i.test(last)) {
      const t = opts.tools.find((x) => x.name === "log_hours");
      if (t) { await t.execute({ place: "Sunrise Home Care", hours: 6, kind: "direct" }, { signal: new AbortController().signal }); text = "Logged 6 hours at Sunrise Home Care for you!"; }
    }
    opts.onText?.({ text, delta: text });
    return { text, truncated: false, modelTierApplied: "default" };
  }
  sample.json = async (prompt) => {
    window.__sampleCalls++;
    if (String(prompt).includes("turn it into JSON")) return deepFreeze(JSON.parse(JSON.stringify(FIX.profile)));
    if (String(prompt).includes("revising")) {
      const r = JSON.parse(JSON.stringify(FIX.tailored));
      r.summary = "Shorter summary for a caregiver headed to nursing school.";
      r.experience[0].bullets = ["Assisted 4 clients per week with activities of daily living (ADLs)", "Helped 40 residents every night"];  // 40 is invented
      r.note = "I made it shorter.";
      window.__lastRevise = String(prompt);
      return deepFreeze(r);
    }
    return deepFreeze(JSON.parse(JSON.stringify(FIX.tailored)));
  };
  sample.limits = async () => ({ maxPromptBytes: 262144, tools: { maxCount: 8 } });
  const downloads = { async save({ filename, data }) { const size = data.size ?? data.length ?? data.byteLength; window.__saved.push({ filename, size, type: data.type || "" }); return { status: "saved" }; } };
  const user = { isOwner: async () => !window.__notMine, canEdit: async () => !window.__notMine, can: async () => null };
  window.claude = { use: async (n) => ({ mcp, sample, downloads, db, user })[n] ?? null };
})();
"""


async def main(libs: Path, shots: Path | None, chrome: str = "/usr/bin/google-chrome", usedb: bool = False) -> int:
    print(f"--- running with {'the stand-in database' if usedb else 'browser storage (no database)'} ---")
    from playwright.async_api import async_playwright

    body = (ROOT / "helper" / "ky.html").read_text()
    html = ('<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>:root{color-scheme:light}body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style></head><body>'
            + body + "</body></html>")
    search = (FIX / "indeed_search.md").read_text()
    details = (FIX / "indeed_details.md").read_text()
    fix = {"search": search, "details": {"default": details}, "profile": PROFILE, "tailored": TAILORED}
    problems: list[str] = []
    ok = lambda cond, msg: (print(("PASS " if cond else "FAIL ") + msg), None if cond else problems.append(msg))

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chrome)
        page = await browser.new_page(viewport={"width": 1000, "height": 1400})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        def serve(rel):
            async def handler(route):
                await route.fulfill(path=str(libs / rel), content_type="application/javascript")
            return handler
        for url, rel in CDN.items():
            await page.route(url, serve(rel))
        await page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(body="", content_type="text/css"))
        await page.add_init_script(STUB % {"fix": json.dumps(fix), "usedb": "true" if usedb else "false"})
        await page.route("http://ky.test/", lambda route: route.fulfill(body=html, content_type="text/html"))
        await page.goto("http://ky.test/")
        await page.wait_for_timeout(800)

        # 1. resume + zip + search
        await page.click("#pasteToggle")
        await page.fill("#resumePaste", RESUME)
        await page.click("#pasteUse")
        await page.fill("#zip", "92501")
        await page.click("#minus"); await page.click("#minus"); await page.click("#minus")  # 2 jobs
        await page.click("#start")
        await page.wait_for_function("document.querySelectorAll('.job').length >= 1 && !document.querySelector('#stop:not([hidden])')", timeout=20000)
        n = await page.locator(".job").count()
        ok(1 <= n <= 2, f"search produced {n} job card(s), asked for 2")
        titles = await page.locator(".job-title").all_inner_texts()
        ok(not any("Instructor" in t or "Registered Nurse" in t for t in titles), f"non-entry jobs filtered out: {titles}")
        await page.wait_for_timeout(400)
        stored = sorted(await page.evaluate("window.__jobs()"), key=lambda j: j["title"])
        ok(len(stored) == n, f"{n} job(s) saved")
        r0 = stored[0]["resume"]
        ok(r0["target_title"] == "", "fact check dropped the made-up CNA headline")
        ok(r0["skills"]["languages"] == ["English", "Spanish"], "odd-shaped skills from Claude are cleaned up")
        ok(len(r0["cover_letter"]) == 3, "cover letter given as one block is split into paragraphs")
        ok("CNA" not in r0["certifications"], "fact check removed the invented CNA certification")
        ok(all("Epic" not in b for b in r0["experience"][0]["bullets"]), "fact check removed the invented Epic bullet")
        ok(len(stored[0]["removedFacts"]) >= 2, "removed facts are recorded for her")
        ptxt = await page.inner_text("#progress")
        if usedb:
            ok("Found 6 new listings, 3 are entry-level" in ptxt, "ZipRecruiter listings are added to Indeed's (and the vet job is dropped)")
            z = await page.evaluate("window.__ky.normalizeJobs(window.__ZIP_JOBS, 'ZipRecruiter')")
            ok(len(z) == 2 and z[0]["url"] == "https://example.com/zr/1" and z[0]["location"] == "Riverside, CA"
               and z[0]["payText"] == "$41,600 - $49,920 a year" and z[0]["payMin"] == 41600 and len(z[0]["posted"]) == 10
               and "Part-time" in z[0]["description"], f"ZipRecruiter results are read correctly: {z[:1]}")
            ok(await page.evaluate("window.__ky.classify('Veterinary Technician ICU')[0]") == "", "veterinary jobs aren't counted as patient care")
            ok(all(a.get("job_role") and a.get("location") == "92501" and a.get("country_admin_code") == "US" for a in await page.evaluate("window.__zipArgs")), "ZipRecruiter gets job_role, ZIP and country")
        else:
            ok("Found 4 new listings" in ptxt and "searched Indeed only" in ptxt, "search carries on, and says so, when ZipRecruiter isn't connected")
        card = await page.locator(".job").first.inner_text()
        ok("Skills match" in card, "job card shows the skills match")
        ok(await page.locator(".job .reasons").count() >= 1, "job card explains why it was picked")
        ok("Apply to" in await page.inner_text("#nextList"), "next steps suggest the best job to apply to")

        # 2. preview, designs, downloads
        await page.locator('[data-act="preview"]').first.click()
        for tpl in ("modern", "classic", "clean"):
            await page.click(f'[data-tpl="{tpl}"]')
            ok(await page.locator(f".paper.tpl-{tpl}").count() == 1, f"preview switches to the {tpl} design")
            if shots and tpl == "modern":
                await page.locator(".dialog").screenshot(path=str(shots / "preview_modern.png"))
        await page.click('[data-rev="Make it shorter"]')
        await page.wait_for_function("document.querySelector('#revStatus').textContent.includes('shorter')", timeout=10000)
        ok("Shorter summary" in await page.inner_text("#paperWrap"), "asking for changes updates the resume preview")
        ok("40 residents" not in await page.inner_text("#paperWrap"), "fact check still blocks invented numbers after a revision")
        await page.click('[data-tab="t"]')
        if await page.locator("[data-qa]").count():
            await page.fill("[data-qa] >> nth=0", "About 20 hours a week")
            await page.click("[data-saveqa]")
            await page.wait_for_function("document.querySelector('#qaStatus').textContent.length > 0 && !document.querySelector('#qaStatus').textContent.includes('Updating')", timeout=10000)
            await page.wait_for_timeout(400)
            facts = (await page.evaluate("window.__settings()"))["profile"]["extra_facts"]
            ok(bool(facts) and facts[0]["answer"] == "About 20 hours a week", "her answers are saved as her own facts")
            ok("About 20 hours a week" in await page.evaluate("window.__lastRevise"), "her answers are sent with the revision")
        await page.click('[data-tab="r"]')
        await page.click('[data-dl="pdf"]'); await page.click('[data-dl="docx"]')
        await page.click('[data-tab="m"]')
        mt = await page.locator('[data-pane="m"]').inner_text()
        ok("Matches" in mt or "didn't list many specific skills" in mt, "job match tab shows the ATS report")
        ok(await page.locator('[data-pane="m"] .checks li').count() == 5, "format checks listed")
        await page.click('[data-tab="c"]'); await page.click('[data-dl="letter"]'); await page.click('[data-dl="letterpdf"]')
        await page.wait_for_timeout(500)
        saved = await page.evaluate("window.__saved")
        names = [s["filename"] for s in saved]
        ok(any(f.endswith("_Resume.pdf") for f in names) and any(f.endswith("_Resume.docx") for f in names) and any(f.endswith("Cover_Letter.docx") for f in names) and any(f.endswith("Cover_Letter.pdf") for f in names), f"resume and cover letter files saved: {names}")
        ok(all(s["size"] and s["size"] > 1500 for s in saved), "saved files are not empty")
        await page.click(".dialog [data-close]")

        # 3. search the whole web (hands off to the chat) and add a job she found
        await page.click("#webBtn")
        ok("near 92501" in await page.input_value("#webMsg"), "whole-web search gives her a message with her ZIP to paste")
        await page.click(".dialog [data-close]")
        await page.click("#addJobBtn")
        await page.fill("#ajTitle", "Nursing Assistant"); await page.fill("#ajCompany", "Example Hills Care Home")
        await page.fill("#ajUrl", "javascript:alert(1)")
        await page.fill("#ajDesc", "Help residents with bathing, dressing and meals. Take vital signs. CNA preferred. $20 - $22 an hour.")
        await page.click("[data-addgo]")
        await page.wait_for_function("!document.querySelector('#ajTitle')", timeout=10000)
        await page.wait_for_timeout(500)
        added = [j for j in await page.evaluate("window.__jobs()") if j["company"] == "Example Hills Care Home"]
        ok(len(added) == 1 and added[0]["via"] == "You added this" and added[0]["resume"], "a job she found herself gets a tailored resume")
        ok(added and added[0]["url"] == "", "a non-web link she pastes is not used")

        # 4. status + chat with a tool call
        await page.select_option(".job select.status >> nth=0", "hired")
        await page.wait_for_timeout(300)
        ok("I got the job!" in await page.locator(".job").first.inner_text(), "status changes to hired")
        ok(await page.evaluate("document.querySelector('#ky').classList.contains('hired')"), "Ky puts on a nurse cap when she's hired")
        ok("hired!" in await page.inner_text("#jobStats"), "progress strip counts the new job")
        await page.click("#fab")
        ok(await page.locator("#chatChips button").count() >= 4, "chat shows suggested questions")
        await page.locator("#chatChips button").first.click()
        await page.wait_for_function("document.querySelector('#chatStop').hidden", timeout=10000)
        ok(await page.locator("#chatLog [data-copymsg]").count() == 1, "long answers get a Copy button")
        await page.fill("#chatIn", "I worked 6 hours at Sunrise today")
        await page.press("#chatIn", "Enter")
        await page.wait_for_function("document.querySelector('#chatStop').hidden && document.querySelectorAll('#chatLog .msg.me').length === 2", timeout=10000)
        log = await page.locator("#chatLog").inner_text()
        ok("Logged 6 hours" in log, "chat tool logged hours and showed a note")
        ok(await page.locator("#chatLog [data-undo]").count() == 1, "chat note has Undo")
        if shots:
            await page.locator("#chat").screenshot(path=str(shots / "chat.png"))
        await page.click("#chatClose")

        # 5. hours form + totals + CSV
        await page.fill("#hPlace", "Sunrise Home Care"); await page.fill("#hHours", "4.5"); await page.click("#hoursForm button[type=submit]")
        await page.wait_for_timeout(300)
        ok((await page.inner_text("#hTotal")).strip() == "10.5", f"hours total is 10.5 (got {await page.inner_text('#hTotal')})")
        await page.fill("#hGoal", "100"); await page.press("#hGoal", "Tab")
        ok("10.5 of 100" in await page.inner_text("#hGoalText"), "goal progress shows")
        await page.click("#hoursCsv"); await page.wait_for_timeout(300)
        ok(any(s["filename"].endswith("_Patient_Care_Hours.csv") for s in await page.evaluate("window.__saved")), "hours CSV saved")

        # 6. alerts turned on from the Claude chat show up on the page (database only)
        if usedb:
            await page.evaluate("(() => { const st = window.__settings(); st.alerts = { on: true, zip: '92501' }; window.__dbSet('settings/main', st); })()")
            await page.wait_for_timeout(300)
            ok("Alerts are on" in await page.inner_text("#alertsText"), "alerts card updates when alerts are turned on elsewhere")
            # a settings save from the page keeps those alerts
            await page.click("#plus"); await page.wait_for_timeout(1200)
            ok((await page.evaluate("window.__settings()")).get("alerts", {}).get("on") is True, "saving settings keeps alerts that were turned on elsewhere")

        # 7. Ky moves don't crash
        await page.click("#ky"); await page.mouse.move(900, 50); await page.wait_for_timeout(400)
        ok(await page.locator("#kyPupils").get_attribute("transform") is not None, "Ky's eyes follow the pointer")

        ok(not errors, f"no page errors: {errors}")
        if shots:
            await page.wait_for_timeout(3500)  # let toasts and acorns finish
            await page.evaluate("window.scrollTo(0, 0)")
            await page.set_viewport_size({"width": 900, "height": 1500})
            await page.screenshot(path=str(shots / "readme.png"))
            await page.set_viewport_size({"width": 1000, "height": 1400})
            await page.screenshot(path=str(shots / "full.png"), full_page=True)
            await page.emulate_media(color_scheme="dark"); await page.set_viewport_size({"width": 400, "height": 900})
            await page.wait_for_timeout(300)
            await page.screenshot(path=str(shots / "phone_dark.png"), full_page=True)
            wide = await page.evaluate("document.documentElement.scrollWidth")
            ok(wide <= 400, f"no sideways scrolling at phone width (page is {wide}px wide)")
        await browser.close()
    print(f"\n{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--libs", required=True, type=Path)
    ap.add_argument("--shots", type=Path)
    ap.add_argument("--chrome", default="/usr/bin/google-chrome")
    ap.add_argument("--db", action="store_true", help="use the stand-in database instead of browser storage")
    a = ap.parse_args()
    if a.shots:
        a.shots.mkdir(parents=True, exist_ok=True)
    sys.exit(asyncio.run(main(a.libs, a.shots, a.chrome, a.db)))
