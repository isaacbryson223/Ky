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
    "target_title": "Patient Care Technician Candidate | BLS Certified",
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
    "skills": {"clinical": ["Vital signs", "Activities of daily living (ADLs)", "Patient transfers"], "technical": [], "languages": ["English", "Spanish"]},
    "volunteer": [],
    "cover_letter": ["P1 about the hospital.", "P2 with two examples.", "P3 about nursing."],
    "keywords_used": ["vital signs"], "questions_for_candidate": ["About how many hours a week do you work?"],
    "why_this_job": "Great hands-on role for nursing school.", "interview_tips": ["Talk about safe transfers."],
}

STUB = r"""
(() => {
  const FIX = %(fix)s;
  window.__saved = []; window.__sampleCalls = 0;
  const mcp = {
    async callTool(server, tool, input) {
      if (tool === "search_jobs") return { content: [], payload: { result: FIX.search } };
      if (tool === "get_job_details") return { content: [], payload: { result: FIX.details[input.job_id] || FIX.details.default } };
      throw { code: "tool_error", message: "unknown" };
    },
  };
  async function sample(input, opts = {}) {
    window.__sampleCalls++;
    let text = "Here's what I know! **Patient-care experience** is hands-on work.\n- Log every shift\n- Keep your supervisor's contact";
    if (opts.tools) {
      const t = opts.tools.find((x) => x.name === "log_hours");
      if (t) { await t.execute({ place: "Sunrise Home Care", hours: 6, kind: "direct" }, { signal: new AbortController().signal }); text = "Logged 6 hours at Sunrise Home Care for you!"; }
    }
    opts.onText?.({ text, delta: text });
    return { text, truncated: false, modelTierApplied: "default" };
  }
  sample.json = async (prompt) => {
    window.__sampleCalls++;
    if (String(prompt).includes("turn it into JSON")) return JSON.parse(JSON.stringify(FIX.profile));
    return JSON.parse(JSON.stringify(FIX.tailored));
  };
  sample.limits = async () => ({ maxPromptBytes: 262144, tools: { maxCount: 8 } });
  const downloads = { async save({ filename, data }) { const size = data.size ?? data.length ?? data.byteLength; window.__saved.push({ filename, size, type: data.type || "" }); return { status: "saved" }; } };
  window.claude = { use: async (n) => ({ mcp, sample, downloads })[n] ?? null };
})();
"""


async def main(libs: Path, shots: Path | None) -> int:
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
        browser = await p.chromium.launch(executable_path="/usr/bin/google-chrome")
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
        await page.add_init_script(STUB % {"fix": json.dumps(fix)})
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
        stored = await page.evaluate("JSON.parse(localStorage.getItem('ky.jobs'))")
        r0 = stored[0]["resume"]
        ok("CNA" not in r0["certifications"], "fact check removed the invented CNA certification")
        ok(all("Epic" not in b for b in r0["experience"][0]["bullets"]), "fact check removed the invented Epic bullet")
        ok(len(stored[0]["removedFacts"]) >= 2, "removed facts are recorded for her")
        ok("Skills match" in await page.locator(".job").first.inner_text(), "job card shows the skills match")

        # 2. preview, designs, downloads
        await page.locator('[data-act="preview"]').first.click()
        for tpl in ("modern", "classic", "clean"):
            await page.click(f'[data-tpl="{tpl}"]')
            ok(await page.locator(f".paper.tpl-{tpl}").count() == 1, f"preview switches to the {tpl} design")
            if shots and tpl == "modern":
                await page.locator(".dialog").screenshot(path=str(shots / "preview_modern.png"))
        await page.click('[data-dl="pdf"]'); await page.click('[data-dl="docx"]')
        await page.click('[data-tab="m"]')
        ok("Matches" in await page.locator('[data-pane="m"]').inner_text(), "job match tab shows the ATS report")
        ok(await page.locator('[data-pane="m"] .checks li').count() == 5, "format checks listed")
        await page.click('[data-tab="c"]'); await page.click('[data-dl="letter"]')
        await page.wait_for_timeout(500)
        saved = await page.evaluate("window.__saved")
        names = [s["filename"] for s in saved]
        ok(any(f.endswith("_Resume.pdf") for f in names) and any(f.endswith("_Resume.docx") for f in names) and any("Cover_Letter" in f for f in names), f"PDF, Word and cover letter saved: {names}")
        ok(all(s["size"] and s["size"] > 1500 for s in saved), "saved files are not empty")
        await page.click(".dialog [data-close]")

        # 3. every design renders a one-page PDF with real text
        pdf_info = await page.evaluate("""() => {
          const s = JSON.parse(localStorage.getItem('ky.jobs'))[0]; const p = JSON.parse(localStorage.getItem('ky.settings')).profile;
          return ['clean','modern','classic'].map(t => { const r = buildPDFProbe(s.resume, p, t); return r; });
        }""".replace("buildPDFProbe", "window.__kyBuildPDF")) if await page.evaluate("typeof window.__kyBuildPDF === 'function'") else None
        if pdf_info:
            ok(all(x["pages"] == 1 for x in pdf_info), f"all three designs fit one page: {pdf_info}")

        # 4. status + chat with a tool call
        await page.select_option(".job select.status >> nth=0", "hired")
        await page.wait_for_timeout(300)
        ok("I got the job!" in await page.locator(".job").first.inner_text(), "status changes to hired")
        await page.click("#fab")
        ok(await page.locator("#chatChips button").count() >= 4, "chat shows suggested questions")
        await page.locator("#chatChips button").first.click()
        await page.wait_for_function("!document.querySelector('#chatStop') || document.querySelector('#chatStop').hidden", timeout=10000)
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

        # 6. Ky moves don't crash
        await page.click("#ky"); await page.mouse.move(900, 50); await page.wait_for_timeout(400)
        ok(await page.locator("#kyPupils").get_attribute("transform") is not None, "Ky's eyes follow the pointer")

        ok(not errors, f"no page errors: {errors}")
        if shots:
            await page.screenshot(path=str(shots / "full.png"), full_page=True)
        await browser.close()
    print(f"\n{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--libs", required=True, type=Path)
    ap.add_argument("--shots", type=Path)
    a = ap.parse_args()
    if a.shots:
        a.shots.mkdir(parents=True, exist_ok=True)
    sys.exit(asyncio.run(main(a.libs, a.shots)))
