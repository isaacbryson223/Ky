# Ky's daily job check

This runs on a schedule in a fresh session. Nobody is watching, so don't ask questions: do the work, then end with one short, friendly message (it becomes her phone notification).

**Never** apply, sign in, create accounts, or submit anything.

## Steps

1. **Get the repo** `isaacbryson223/ky` (attach it, or `git clone https://github.com/isaacbryson223/ky`), then `pip install --break-system-packages -e .` inside it.

2. **Read her helper's data** (the artifact URL is in your prompt), using the artifact database tool:
   - `settings/main` → `zip`, `count`, `resumeText`, `profile`, `alerts`, `prefs` (her "Fine-tune my search" choices: `roles`, `schedule`, `shifts`).
   - If `alerts.on` isn't true, stop quietly with: "Ky job alerts are turned off."
   - List the `jobs` collection → collect every document id (these are the jobs she's already seen).
   - Save `profile` to `profile.json` and the ids to `seen.json` (a JSON list).

3. **Search Indeed.** Get her search terms with `ky terms --roles <prefs.roles joined by commas>` (leave `--roles` off if she has no `prefs.roles`). Search once per term with the Indeed connector: `country_code: "US"`, `location: <zip>`, plus `job_type: <prefs.schedule>` when it is `parttime` or `fulltime`.
   Save each result's text to `search_1.md`, `search_2.md`, … exactly as returned.
   - **ZipRecruiter:** if the ZipRecruiter connector is available, search it once per term too (her ZIP as the location). Turn its listings into a JSON list in the `jobs.json` shape from `skills/ky/WEBSEARCH.md` step 5 (`"source": "ZipRecruiter"`, `"via": "ZipRecruiter"`) and save it as `zip_jobs.json`.
   - **The whole web:** only if `prefs.web` is true, do a short web search (about 5 queries and up to 10 postings) following `skills/ky/WEBSEARCH.md` steps 3 to 5, and save those as `web_jobs.json`.

4. **Score and rank:**
   ```
   ky score search_*.md [zip_jobs.json] [web_jobs.json] --profile profile.json --seen seen.json --limit 8 [--shifts <prefs.shifts joined by commas>] > ranked.json
   ```
   Drop anything with red flags other than "Posting is over 45 days old".

5. **Read details** for the top Indeed jobs (up to `count`, at most 5) with the Indeed connector's `get_job_details` (`job_id` = the job's `external_id`). Save each to `detail_<n>.md`. ZipRecruiter and web jobs already have their descriptions. Re-score them all together:
   ```
   ky score detail_*.md [zip_jobs.json] [web_jobs.json] --profile profile.json --seen seen.json --limit <count, max 5> [--shifts ...] > top.json
   ```
   If nothing is left, skip to step 8.

6. **Tailor a resume for each job.** For each job in `top.json`, follow `agent/prompts/tailor.md` (her profile YAML = `profile.json`; the job = title, employer, location, description). Write the JSON reply to `tailored_<key>.json`, then fact-check it:
   ```
   ky check tailored_<key>.json --profile profile.json --fix tailored_<key>.clean.json
   ```
   Use the cleaned file. Keep the `problems` list as `removedFacts`.

7. **Save each job into her helper** with one batch write to the `jobs` collection, document id = the job's `key`, data in the shape the helper page reads:
   ```json
   {
     "key": "<key>", "title": "<title>", "company": "<employer>", "location": "<location>",
     "jobId": "<external_id>", "posted": "<posted>", "type": "<schedule>", "via": "<via>",
     "payText": "<pay as listed, e.g. $20 - $27 an hour>", "payMin": <pay_min>, "payMax": <pay_max>,
     "url": "<url>", "description": "<description, first 9000 characters>",
     "tier": "<tier>", "roleLabel": "<role_label>", "setting": "",
     "clinical": <clinical_score>, "fit": <fit_score>,
     "badges": [<badges>], "flags": [<red_flags>], "missing": [<missing>], "notes": [],
     "foundAt": "<now ISO>", "source": "alerts", "seen": false, "status": "new",
     "resume": <the cleaned tailored JSON>, "removedFacts": [<problems>]
   }
   ```
   These are new documents, so no `if_version` is needed.

8. **Record the run:** update `settings/main` (pin the `if_version` you read) with `{"alerts": {...existing alerts fields, "lastRun": "<now ISO>"}}`.

9. **Check her reminders** from the `jobs` you listed in step 2: jobs with `status: "applied"`, an `appliedOn` 7+ days ago and no `followedUpOn` need a follow-up; jobs with `status: "interview"` may need practice. Mention at most one reminder in the message.

10. **Finish with her notification message** (one or two short lines, Ky's voice):
   - New jobs: "🐿️ Found 2 new jobs near 95814! CNA at Example Care ($21–24/hr) and PCT at Example Hospital. Your resumes are ready in Ky."
   - Nothing new: "🐿️ No new jobs near 95814 today. I'll check again tomorrow!"
   - With a reminder, add one line: "Also: it's been a week since you applied to Example Care. Want me to write a follow-up? Tap Ask Ky."
   - A problem (Indeed disconnected, usage limit): say what she can do in one sentence, e.g. "Indeed needs reconnecting in Claude settings so I can keep searching."
