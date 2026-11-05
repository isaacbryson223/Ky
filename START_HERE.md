# Start Agent Ky 🐿️

## For her: the only thing to do

Open Claude (the app or claude.ai), start a **new chat**, and paste this whole message:

```
Hi Claude! Please open my job helper, Agent Ky 🐿️. I'm not technical, so please do all of this for me and don't ask me technical questions.

1. Get the file helper/ky.html from the public GitHub repo isaacbryson223/Ky. Attach the repo, clone https://github.com/isaacbryson223/Ky, or download https://raw.githubusercontent.com/isaacbryson223/Ky/main/helper/ky.html. Read the whole file and don't change anything in it.

2. Check my artifacts for one called "Agent Ky".
   - If I have one and its <meta name="ky-version"> is the same as or newer than the repo file's, just open it.
   - If mine is older, read it, then republish the repo file to that same artifact URL so my saved jobs and hours stay.

3. If I don't have one, publish helper/ky.html as a new artifact. Use the icon "search", the description "Ky the squirrel finds entry-level patient-care jobs near me and writes a tailored resume for each one.", and exactly these capabilities:
{"mcp":{"servers":[{"server":"Indeed","tools":["search_jobs","get_job_details"]}]},"sample":{"images":true},"downloads":true,"db":{"rules":[{"path":"jobs","read":"owner","write":"owner"},{"path":"settings","read":"owner","write":"owner"},{"path":"hours","read":"owner","write":"owner"}]}}
Keep it private and don't share it.

4. Ky finds jobs through Claude's Indeed connector. If Indeed isn't connected for me, show me the button to connect it.

5. Open Ky for me. Then reply with only a short, friendly hello from Ky and these three steps: add my resume, type my ZIP code, then pick how many jobs and tap "Start the search". Remind me to tap "Allow" when Claude asks if Ky can use Indeed and Claude.

If something doesn't work, tell me in one simple sentence what to do. For anything else I ask later (job alerts, help applying), follow skills/ky/SKILL.md in the same repo.
```

Ky will pop up as a little squirrel helper. Then:

1. **Add your resume.** A PDF, a Word file, or a photo of a paper resume all work.
2. **Type your ZIP code.**
3. **Pick how many jobs** you want right now, and tap **Start the search**.

When Claude asks whether Ky can use Indeed and Claude, tap **Allow**.

Ky finds entry-level healthcare jobs near you that give real patient-care hours, then writes a resume and cover letter for each one. Tap **Download PDF** to save a resume, then **Open job posting** to apply.

**Have a question?** Tap **Ask Ky** in the bottom corner. Ask anything about applying, interviews, certifications, or patient-care hours. You can even say "I worked 8 hours at Sunrise today" and Ky will add it to your hours log.

**Track your hours.** Once you start working, log each shift under **Your patient-care hours** (with your supervisor's name and contact). Tap **Download my hours** when a school asks.

**Want Ky to keep watching?** Tap **Turn on job alerts** in the helper, copy the message it shows you, and send it in your Claude chat. Ky will check every morning and send you a notification when it finds a new job.

**Coming back later?** Paste the same message again, or just say "Hi Ky" in a new Claude chat. Ky opens your saved helper, with all your jobs and hours.

---

## For whoever is setting this up (Isaac)

Before she starts, check that her Claude account can:

- **Connect Indeed**: Ky searches jobs through Claude's Indeed connector. Ky will show her a Connect button if it's missing.
- **Run scheduled tasks**: needed for the daily job alerts.
- **Use Claude in Chrome** (optional): only needed if she wants Ky to help fill in applications.

She needs her own Claude account; a link to someone else's Ky page won't save her data. She doesn't need a GitHub account, because the repo is public.

Her resume and jobs are saved in her own private Ky page in her Claude account. Nothing personal is ever stored in this GitHub repo.
