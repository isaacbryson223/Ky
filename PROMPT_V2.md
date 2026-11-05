# Agent Ky v2 — Improvement Brief

> Give this file to a coding agent working in the `isaacbryson223/ky` repo. It builds on what already exists (read `README.md`, `PROMPT.md`, `skills/ky/SKILL.md` and `helper/ky.html` first). Work through the sections in order, keep everything that works, and finish with the checks in section 10.

---

## 0. Who Ky is for, in one paragraph

Ky helps one person who wants to become a nurse. She has **no AI experience**. She opens Ky inside her Claude, adds her resume, types her ZIP code, picks how many jobs she wants, and taps Start. Ky finds entry-level healthcare jobs near her that give **real hands-on patient care**, ranks them, and writes an honest, ATS-friendly resume and cover letter for each one. Ky is a **cute, kind, encouraging squirrel**. Every screen must be obvious to someone who has never used a chatbot: one clear next step at a time, friendly plain words, no jargon.

## 1. What v1 already does (don't break it)

- `helper/ky.html` — the squirrel helper page (runs inside her Claude as an artifact): resume upload (PDF / Word / photo / paste), ZIP, job count, Indeed search through her own Indeed connector, scoring (patient-care hours + fit), tailoring through her own Claude, fact check, PDF and Word downloads, cover letter, apply warning, alerts card, saved jobs with status.
- `skills/ky/SKILL.md` — setup in one pasted message, alerts, apply help. `ALERTS.md`, `APPLY.md`.
- `ky/` — Python engine: sources, dedupe, scoring, fact guard, CLI (`ky score`, `ky check`, `ky search`), tests.
- Storage: the helper's private database, collections `jobs/<key>` and `settings/main`, both owner-only.

## 2. Hard constraints (the runtime Ky lives in)

- The helper is a single HTML file published as a Claude artifact. It talks to the outside world **only** through runtime capabilities: `mcp` (her Indeed connector), `sample` (her own Claude, memoryless per call, optional page tools), `downloads` (save a file after she confirms), `db` (private database). Design every feature to degrade kindly when a capability is missing.
- No `window.print()`, no `<a download>`, no `alert/confirm/prompt`, no network fetches except approved CDN scripts. Files are produced in the page (jsPDF, docx) and saved through `downloads.save`.
- Each `sample` call spends **her** Claude usage. Never call it from a loop or a timer; only on her action. Show "Thinking…" until text arrives, offer Stop on anything long.
- Personal data never goes into the GitHub repo.
- Light and dark themes, works at 400px wide, keyboard accessible, respects reduced motion.

## 3. NEW: "Ask Ky" chat (the headline feature)

A small chat inside the helper where she can ask Ky anything about **job applications, clinical / patient-care hours, nursing school prep, certifications and interviews**.

### 3.1 How it looks and feels

- A round **Ask Ky** button with Ky's face, fixed to the bottom-right corner (respect safe-area insets). It's always there.
- Tapping it opens a chat panel: a side sheet on desktop (about 400px wide), a full-screen sheet on phones. Header: Ky's face, "Ask Ky", a close button.
- When the chat is empty, Ky greets her and shows **suggested questions** as tappable chips, for example:
  - "What counts as patient-care hours?"
  - "Should I apply if I don't have my CNA yet?"
  - "How do I follow up after applying?"
  - "Which job here is best for nursing school?"
  - "What should I wear to a hospital interview?"
  - "How many hours have I logged?"
- Answers stream in as Ky writes them. Short paragraphs and simple bullet lists only (render a tiny safe subset of Markdown: paragraphs, `- ` bullets, `**bold**`). A Stop button while Ky is writing.
- Under the input: "Ky can make mistakes. Double-check important details with the employer or school."
- The conversation is remembered on her device (browser storage, last ~30 messages) with a "Start over" link.

### 3.2 Entry points from the rest of the helper

- Each job card gets **Ask Ky about this job**: opens the chat focused on that job (its details are included in what Ky knows) with suggestions like "Is this a good job for me?", "What will I do on a shift?", "How should I answer 'why this job?'".
- Jobs marked **I applied** for 7+ days show a **Time to follow up** badge and a **Write a follow-up** button: opens the chat and asks Ky for a short follow-up email she can copy and send herself.
- Jobs marked **Got an interview** show **Practice my interview**: opens the chat and starts a practice session (Ky asks one question at a time, gives kind feedback, uses her real experience).

### 3.3 What Ky knows in the chat

Each call sends (as the first, standing "instructions" turn): Ky's persona and rules (3.4), plus a compact, current summary of her situation:
- first name, city, certifications, her past roles (with which ones were patient care), education
- her jobs (up to 15): title, employer, pay, status, date applied, badges, missing requirements, ratings
- her hours log totals (total, direct patient care, by place) and her goal if she set one
- the focused job's full description and the tailored resume summary, when the chat was opened from a job

Never include her phone number or email in chat context.

### 3.4 Ky's chat persona and rules (write into the page as the standing instruction)

- Ky is a warm, upbeat squirrel and a knowledgeable friend about entry-level healthcare jobs and the path to nursing. Short answers first (2–6 sentences or a short list), offer to go deeper.
- Stay on topic: job searching, applications, resumes, cover letters, interviews, workplace basics in healthcare jobs, certifications (CNA, BLS/CPR, phlebotomy, EKG, MA, EMT), patient-care/clinical hours, nursing school prerequisites and applications, balancing work and school. Gently steer back if asked about unrelated things.
- **Clinical hours vs. patient-care experience:** explain the difference kindly when it comes up. "Clinical hours" in nursing usually means the supervised clinical rotations students complete *during* nursing school. What she builds now is **healthcare or patient-care experience**. Many nursing programs don't require a set number of experience hours to apply, though experience (especially as a CNA) can strengthen an application, and some programs require a CNA certificate or healthcare experience as a prerequisite. Other programs (for example physician assistant programs) do count patient-care hours. **Requirements vary by school** — always tell her to check each program's official admissions page, and never state a specific program's requirement as fact.
- What usually counts as **direct patient care**: hands-on work with patients (vitals, ADLs, transfers, feeding, specimen collection, monitoring). Front-desk, transport-only or scribe work may count as healthcare exposure but often not as hands-on care.
- Encourage good habits: log every shift, keep supervisor names and contact info, ask for a reference letter before leaving a job.
- Honesty: never suggest putting anything untrue on a resume or application. If she lacks a requirement, explain options (apply anyway when it says "preferred", employers that train, getting certified).
- Not legal, medical or financial advice. For pay/benefits/visa/legal questions, say what's generally true and point her to the employer or an official source. Never give medical advice about patients.
- Never ask for or repeat passwords, SSNs, bank info.
- If she seems stressed or discouraged, be supportive first, then give one small next step.

### 3.5 Chat actions (page tools, only when the runtime supports tools)

Offer Claude a small set of page functions so the chat can *do* simple things she asks for:
- `log_hours({date, place, hours, kind, supervisor?, notes?})` — adds an hours entry ("I worked 8 hours at Sunrise yesterday"). Additive and shown in the chat with an **Undo** button.
- `set_job_status({key, status})` — "I applied to the Example Hospital one" → marks it applied (also undoable).
Keep tool results tiny. If tools aren't available, Ky answers normally and tells her where to tap.

## 4. NEW: Patient-care hours log

A section "Your patient-care hours":
- Big total, plus "direct patient care" total. Optional **goal** (her own number, e.g. what a program asks for) with a progress bar. Never invent a goal for her.
- **Log hours** form: date (defaults to today), place (pick from jobs she marked "I got the job!", or type one), hours, kind (Direct patient care / Other healthcare / Volunteer), supervisor name, supervisor contact, notes.
- Recent entries list with delete (inline "Are you sure?" step, no browser dialogs).
- **Download my hours (CSV)** for applications, through `downloads`.
- Reminder text: "Before you leave any job, ask your supervisor to confirm your hours and write down how to reach them."
- Stored in the private database collection `hours/<id>` (owner-only rule added to the artifact's `db` rules).
- Job status gets a new option **I got the job!** (celebrate, then suggest logging hours).

## 5. NEW: ATS check on every resume

In the resume preview, a **Job match** report:
- Keywords the posting asks for (from a healthcare keyword vocabulary with synonyms: vital signs, ADLs, patient transfers, infection control, patient safety, documentation, EHR/Epic, HIPAA, specimen collection, EKG, blood glucose, dementia care, customer service, teamwork, bilingual, CPR/BLS, …): which ones her resume covers, and which ones aren't on her resume ("only add these if they're true for you").
- A simple score ("Matches 9 of 11 skills this job lists") shown on the job card too.
- Format checks: one page, real text (not an image), standard section headings, contact info present, no tables/columns. All Ky's PDFs should pass; show green checks.
- Port the same keyword logic to Python (`ky/ats.py`, `ky ats` CLI) so the daily check can store the same report.

## 6. NEW: Resume designs

Three designs she can switch between in the preview (her choice is remembered):
- **Clean** — current layout, teal section headings.
- **Modern** — a soft colored header band with her name, thin accent bars on section headings.
- **Classic** — serif type, centered name, black rules; good for conservative employers.
All three: one page, single column, real selectable text, standard headings, so they stay ATS-friendly. PDF and Word downloads follow the chosen design (Word: matching fonts and colors).

## 7. Search improvements

- A collapsed **Fine-tune my search** area under the three main steps (main flow stays three steps):
  - job types to include (chips: CNA, Patient care tech, ER tech, Caregiver/Home health, Medical assistant, Phlebotomy, Behavioral health, EKG/Monitor tech, Sitter/Transport) — defaults to the v1 set
  - schedule: Any / Part-time / Full-time
  - shifts she can work: Days / Evenings / Nights / Weekends (used in the fit rating)
- Saved in `settings/main.prefs`; the daily alerts honor them (update `skills/ky/ALERTS.md`).

## 8. Small polish

- Time-of-day greeting ("Good morning!") and a gentle tip rotation in Ky's bubble.
- Job card buttons in two clear rows; Word download lives in the preview.
- Every error says what happened and what to tap next.

## 9. Docs

- `skills/ky/SKILL.md`: new `db` rule for `hours`; mention Ask Ky and the hours log in Ky's intro; Claude in chat can read the hours log to answer "how many hours do I have?".
- `README.md` and `START_HERE.md`: describe Ask Ky and hours tracking in plain words.

## 10. Definition of done

- Helper script parses (`node --check`), page renders at desktop and phone width in light and dark.
- Ask Ky: chips work, answers stream, Stop works, context includes jobs/hours/focused job, tools log hours and set status with Undo, works without tools.
- Hours log: add, delete with confirm, totals, goal progress, CSV download.
- ATS report shows in preview and score on cards; Python `ky ats` matches the page's logic; tests pass.
- Three resume designs render in preview, PDF and Word.
- Fine-tune options saved and used by search and alerts.
- Test copy republished with the new `db` rules; database read check passes; everything pushed to `main`.
