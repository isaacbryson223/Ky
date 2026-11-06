"""Replay a real Ky helper's saved data in a browser and open every resume.

Exports from a helper's database (jobs/*.json and settings/main.json, as the
artifact database tool writes them with out_dir) are loaded into the stand-in
database. The page then runs under a content security policy like the one
Claude puts around artifacts, and this script:

  - opens every job's resume, switches all three designs, and downloads the
    PDF, Word file and cover letter (PDF and Word) for each one
  - checks every downloaded file: PDFs open, have real text and one page,
    Word files open and contain her name
  - uploads her resume as a PDF and as a Word file and checks the page read it

Nothing personal is stored in the repo: point --data at a folder outside it.

    python tests/e2e/replay_saved_data.py --libs /path/to/libs --data /path/to/export [--chrome PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import run_helper_e2e as E  # noqa: E402

CSP = ("default-src 'none'; "
       "script-src 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
       "style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
       "img-src data: blob:; worker-src blob:; connect-src 'none'")

# Record what the page downloads and what it asks Claude to read.
SPY = r"""
(() => {
  window.__files = {}; window.__prompts = [];
  const orig = window.claude.use;
  window.claude.use = async (n) => {
    const v = await orig(n);
    if (n === "downloads" && v) return { save: async ({ filename, data }) => {
      const buf = data instanceof Blob ? new Uint8Array(await data.arrayBuffer()) : typeof data === "string" ? new TextEncoder().encode(data) : new Uint8Array(data);
      let s = ""; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
      window.__files[filename] = btoa(s);
      return v.save({ filename, data });
    } };
    if (n === "sample" && v) { const f = async (i, o) => v(i, o); f.json = async (i, o) => { window.__prompts.push(String(i)); return v.json(i, o); }; f.limits = v.limits; return f; }
    return v;
  };
})();
"""


def load_export(folder: Path) -> dict:
    seed = {}
    for f in sorted((folder / "jobs").glob("*.json")):
        d = json.loads(f.read_text())
        seed[f"jobs/{f.stem}"] = d.get("data", d)
    s = folder / "settings" / "main.json"
    if s.exists():
        d = json.loads(s.read_text())
        seed["settings/main"] = d.get("data", d)
    return seed


def check_pdf(raw: bytes, name: str) -> tuple[bool, str]:
    from pypdf import PdfReader
    try:
        r = PdfReader(io.BytesIO(raw))
        text = "".join(p.extract_text() or "" for p in r.pages)
        ok = len(text.strip()) > 200 and (name.split()[0].lower() in text.lower())
        return ok, f"{len(r.pages)} page(s), {len(text)} chars of text"
    except Exception as e:  # noqa: BLE001
        return False, f"won't open: {e}"


def check_docx(raw: bytes, name: str) -> tuple[bool, str]:
    import docx
    try:
        d = docx.Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in d.paragraphs)
        return (len(text.strip()) > 100 and name.split()[0].lower() in text.lower()), f"{len(d.paragraphs)} paragraphs"
    except Exception as e:  # noqa: BLE001
        return False, f"won't open: {e}"


def resume_files(resume_text: str, outdir: Path) -> tuple[Path, Path]:
    """Her resume text as a real PDF and a real Word file, for the upload test."""
    import docx
    from weasyprint import HTML
    paras = "".join(f"<p>{line}</p>" for line in resume_text.splitlines() if line.strip())
    pdf = outdir / "resume.pdf"
    HTML(string=f"<html><body style='font-family:sans-serif;font-size:11pt'>{paras}</body></html>").write_pdf(str(pdf))
    d = docx.Document()
    for line in resume_text.splitlines():
        if line.strip():
            d.add_paragraph(line)
    dx = outdir / "resume.docx"
    d.save(str(dx))
    return pdf, dx


async def wait_for(page, expr: str, timeout: float = 15.0) -> None:
    """Poll a JS expression (wait_for_function needs eval, which the CSP blocks)."""
    loop = asyncio.get_running_loop(); end = loop.time() + timeout
    while loop.time() < end:
        if await page.evaluate(expr):
            return
        await asyncio.sleep(0.2)
    raise TimeoutError(expr)


async def main(libs: Path, data: Path, chrome: str) -> int:
    from playwright.async_api import async_playwright

    seed = load_export(data)
    if "settings/main" not in seed:
        print(f"FAIL {data} has no settings/main.json. Export the settings collection too (it holds her resume).")
        return 1
    settings = seed.get("settings/main") or {}
    profile = settings.get("profile") or {}
    name = profile.get("name") or "Resume"
    jobs = {k: v for k, v in seed.items() if k.startswith("jobs/")}
    print(f"Replaying {len(jobs)} saved job(s) for {name.split()[0]}…")

    body = (E.ROOT / "helper" / "ky.html").read_text()
    html = ('<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
            '<style>:root{color-scheme:light}body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style></head><body>'
            + body + "</body></html>")
    fix = {"search": (E.FIX / "indeed_search.md").read_text(), "details": {"default": (E.FIX / "indeed_details.md").read_text()},
           "profile": profile or E.PROFILE, "tailored": E.TAILORED}
    problems: list[str] = []

    def ok(cond, msg):
        print(("PASS " if cond else "FAIL ") + msg)
        if not cond:
            problems.append(msg)

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chrome)

        async def new_page(with_seed: bool, not_mine: bool = False):
            page = await browser.new_page(viewport={"width": 1000, "height": 1300})
            errs: list[str] = []
            page.on("pageerror", lambda e: errs.append(f"page error: {e}"))
            page.on("console", lambda m: errs.append(f"console {m.type}: {m.text}") if m.type == "error" or "Refused" in m.text else None)

            def serve(rel):
                async def handler(route):
                    await route.fulfill(path=str(libs / rel), content_type="application/javascript")
                return handler
            for url, rel in E.CDN.items():
                await page.route(url, serve(rel))
            await page.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css"))
            if with_seed:
                await page.add_init_script(f"window.__SEED = {json.dumps(seed)};")
            if not_mine:
                await page.add_init_script("window.__notMine = true;")
            await page.add_init_script(E.STUB % {"fix": json.dumps(fix), "usedb": "true"})
            await page.add_init_script(SPY)
            await page.route("http://ky.test/", lambda r: r.fulfill(body=html, content_type="text/html"))
            await page.goto("http://ky.test/")
            return page, errs

        # ---- 1. open and download every saved resume ----
        page, errs = await new_page(True)
        await wait_for(page, f"document.querySelectorAll('.job').length === {len(jobs)}")
        ok(True, f"all {len(jobs)} saved jobs show up")
        ok(await page.evaluate("!document.querySelector('#envNotice:not([hidden])')"), "no warning banner on load")
        if settings.get("zip"):
            zipv = await page.evaluate("document.querySelector('#zip').value")
            ok(zipv == str(settings["zip"]), f"her saved ZIP code is filled in ({zipv or 'empty'})")
        keys = await page.evaluate("[...document.querySelectorAll('.job')].map((c) => c.dataset.key)")
        for key in keys:
            title = await page.inner_text(f'.job[data-key="{key}"] .job-title')
            btn = page.locator(f'.job[data-key="{key}"] [data-act="preview"]')
            if not await btn.count():
                ok(False, f"{title}: no 'See my resume' button"); continue
            await btn.click()
            try:
                await page.wait_for_selector(".dialog .paper", timeout=5000)
            except Exception:  # noqa: BLE001
                toast = await page.evaluate("document.querySelector('.toast')?.textContent || ''")
                ok(False, f"{title}: resume didn't open ({toast or 'no message'})"); continue
            paper = await page.inner_text("#paperWrap")
            ok(name.split()[0] in paper and len(paper) > 400, f"{title}: resume opens ({len(paper)} chars)")
            for tpl in ("modern", "classic", "clean"):
                await page.click(f'[data-tpl="{tpl}"]')
            ok(await page.locator(".paper.tpl-clean").count() == 1, f"{title}: designs switch")
            await page.click('[data-dl="pdf"]'); await page.click('[data-dl="docx"]')
            await page.click('[data-tab="c"]'); await page.click('[data-dl="letterpdf"]'); await page.click('[data-dl="letter"]')
            await page.click('[data-tab="m"]'); await page.click('[data-tab="t"]')
            await page.wait_for_timeout(700)
            await page.click(".dialog [data-close]")
            # the card's own Download PDF button too
            await page.locator(f'.job[data-key="{key}"] [data-act="pdf"]').click()
            await page.wait_for_timeout(400)

        files = await page.evaluate("window.__files")
        pdfs = [f for f in files if f.endswith(".pdf")]
        docs = [f for f in files if f.endswith(".docx")]
        ok(len(pdfs) >= len(jobs) and len(docs) >= len(jobs), f"files downloaded: {len(pdfs)} PDFs, {len(docs)} Word files")
        for fn, b64 in sorted(files.items()):
            raw = base64.b64decode(b64)
            good, info = check_pdf(raw, name) if fn.endswith(".pdf") else check_docx(raw, name)
            if "Resume.pdf" in fn:
                good = good and info.startswith("1 page")
            ok(good, f"{fn}: {info}")
        ok(not errs, f"no errors while opening resumes: {errs[:5]}")
        await page.close()

        # ---- 1b. phone size: the resume window fits and its buttons are reachable ----
        page, errs = await new_page(True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await wait_for(page, f"document.querySelectorAll('.job').length === {len(jobs)}")
        await page.locator('.job [data-act="preview"]').first.click()
        await wait_for(page, "!!document.querySelector('.dialog .paper')", 5)
        box = await page.locator(".dialog").bounding_box()
        ok(box and box["x"] >= 0 and box["x"] + box["width"] <= 390 and box["height"] <= 844, f"resume window fits a phone screen {box}")
        await page.locator('[data-dl="pdf"]').scroll_into_view_if_needed()
        ok(await page.locator('[data-dl="pdf"]').is_visible() and await page.locator(".dialog [data-close]").is_visible(), "Download and Close are reachable on a phone")
        ok(not errs, f"phone: no errors {errs[:3]}")
        await page.close()

        # ---- 1c. a job Claude saved from the chat in the engine's format (resume stored as text) ----
        any_resume = next(v["resume"] for v in jobs.values() if v.get("resume"))
        odd = {"title": "Patient Care Technician", "employer": "Example Valley Hospital", "location": "Riverside, CA",
               "url": "https://example.com/careers/1", "description": "Hospital PCT. Vital signs, ADLs.", "source": "web", "via": "Example Valley Hospital careers",
               "clinical_score": 88, "fit_score": 70, "tier": "A", "role_label": "Patient Care Technician", "red_flags": [], "badges": ["Paid training"],
               "missing": [], "pay_min": 22, "pay_max": 26, "pay_period": "hour", "seen": False, "status": "new",
               "resume": json.dumps(any_resume), "removedFacts": []}
        seed["jobs/jodd1"] = odd
        page, errs = await new_page(True)
        await wait_for(page, f"document.querySelectorAll('.job').length === {len(jobs) + 1}")
        card = await page.inner_text('.job[data-key="jodd1"]')
        ok("Example Valley Hospital" in card and "$22 - $26 an hour" in card and "via Example Valley Hospital careers" in card, "a job saved from the chat shows its employer, pay and source")
        await page.locator('.job[data-key="jodd1"] [data-act="preview"]').click()
        await wait_for(page, "!!document.querySelector('.dialog .paper')", 5)
        ok(len(await page.inner_text("#paperWrap")) > 400, "its resume (saved as text) opens")
        ok(not errs, f"chat-saved job: no errors {errs[:3]}")
        await page.close()
        del seed["jobs/jodd1"]

        # ---- 1d. someone else's Ky ----
        page, errs = await new_page(False, not_mine=True)
        await wait_for(page, "!document.querySelector('#envNotice').hidden", 8)
        ok("belongs to someone else" in await page.inner_text("#envNotice"), "someone else's Ky says so plainly")
        await page.fill("#zip", "92501")
        ok(await page.evaluate("document.querySelector('#start').disabled"), "and doesn't let her start a search that couldn't be saved")
        await page.close()

        # ---- 2. upload her resume as PDF and as Word ----
        resume_text = settings.get("resumeText") or ""
        if resume_text:
            with tempfile.TemporaryDirectory() as td:
                pdf, dx = resume_files(resume_text, Path(td))
                for f in (pdf, dx):
                    page, errs = await new_page(False)
                    await page.wait_for_timeout(1200)  # let the deferred libraries load
                    await page.set_input_files("#resumeFile", str(f))
                    try:
                        await wait_for(page, "(document.querySelector('#resumeName')?.textContent || '').length > 0 || !document.querySelector('#errorBox').hidden")
                        if not await page.evaluate("document.querySelector('#errorBox').hidden"):
                            raise RuntimeError("error shown")
                        got = await page.evaluate("JSON.parse(localStorage.getItem('ky.settings') || '{}').resumeText || window.__settings()?.resumeText || ''")
                        first_line = next((ln.strip() for ln in resume_text.splitlines() if len(ln.strip()) > 8), "")
                        words = [w for w in first_line.split() if len(w) > 3][:3]
                        ok(len(got) > 200 and all(w.lower() in got.lower() for w in words), f"{f.suffix} upload is read ({len(got)} chars)")
                    except Exception:  # noqa: BLE001
                        err = await page.evaluate("document.querySelector('#errorBox:not([hidden])')?.textContent || ''")
                        ok(False, f"{f.suffix} upload failed: {err or 'nothing happened'}")
                    ok(not errs, f"{f.suffix} upload: no errors {errs[:3]}")
                    await page.close()
        await browser.close()

    print(f"\n{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--libs", required=True, type=Path)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--chrome", default="/usr/bin/google-chrome")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.libs, a.data, a.chrome)))
