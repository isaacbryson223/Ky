# Changelog

## v2.5
- Ky searches **ZipRecruiter** as well as Indeed (both free Claude connectors). If ZipRecruiter isn't connected, Ky searches Indeed and says so.
- **Search the whole web**: a button that hands off to her Claude chat, which checks hospital and clinic career pages, nursing homes and home-care agencies, county, state and VA jobs, and other job sites, then adds the best jobs to her helper with tailored resumes (`skills/ky/WEBSEARCH.md`). Daily alerts can do a short version too ("Also search the whole web every morning").
- **Add a job I found**: paste any job post (LinkedIn, a hospital site, a flyer) and Ky writes a resume for it.
- Job cards show where each job came from. The engine accepts web/ZipRecruiter jobs as JSON with pay written as text.

## v2.4 (fixes from an independent code review)
- Every resume is fact-checked before it's kept, including the headline and education details; odd-shaped replies from Claude are cleaned up instead of breaking buttons.
- A failed save no longer makes her job list look empty; Ky retries once and tells her if it still can't save.
- Settings saves wait until her saved settings have loaded and merge onto the latest copy, so a new visit can't wipe her resume or turn off her alerts.
- "Start" waits until her saved jobs have loaded, and a new search never overwrites a job she already marked applied.
- One failed search no longer stops the whole search; Ky stops "working" when there's an error.
- Job links must be real web addresses; job details only trust the posting's header.
- Certifications match whole words ("PALS" isn't "palsy", "CNA" isn't "CNAs").
- Files are built inside the download step, so a library hiccup shows a message instead of doing nothing. Libraries load without blocking the page.
- Friendlier upload errors (unsupported files, photo formats); keyboard-reachable file picker; no iPhone zoom on small fields; dialogs return focus; "Not for me" has Undo; the alerts card updates live.
- Browser test now runs with a stand-in database and malformed Claude replies too.

## v2.3
- Ky puts on a little nurse cap once she gets a job.
- Progress strip on "Your jobs": jobs found, applied, interviews, hours logged.
- "I followed up" clears the follow-up reminder; daily alerts mention a follow-up when one is due.

## v2.2
- In the resume preview she can ask for changes ("Make it shorter", "Focus more on patient care", or her own words) and Ky updates the resume. The fact check still runs on every update.
- She can answer Ky's "make it stronger" questions right in the Tips tab. Her answers are saved as her own facts and used in this resume and future ones.
- More accurate resume reading, a clear message for iPhone HEIC photos, keyboard focus stays inside open dialogs.

## v2.1
- "Your next steps" card: the best job to apply to, follow-ups due, interview practice, logging shifts at a new job, turning on alerts.
- Faster: searches, job details and resume writing run a few at a time.
- Job cards explain why each job was picked. Chat answers have a Copy button. Cover letters download as PDF too.
- Hours milestones get a celebration. Ky waves hello, wags faster on hover, glances at the box you're typing in, and nibbles an acorn while working.

## v2.0
- **Ask Ky** chat for questions about applications, interviews, certifications and patient-care hours, with follow-up emails, interview practice, and hours logging / job status changes (with Undo).
- Patient-care hours log with a goal, progress and CSV download.
- Job match (ATS) report and three resume designs (Clean, Modern, Classic).
- Fine-tune search: job types, schedule, shifts.
- Squirrel moves: eyes follow the pointer, ear twitches, tap-to-pet tricks, naps, a running squirrel while searching, acorn rain.

## v1.0
- Squirrel helper: resume upload, ZIP code, job count, Indeed search, patient-care and fit ratings, tailored fact-checked resumes and cover letters (PDF and Word), apply warning, daily job alerts.
