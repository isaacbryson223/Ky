<p align="center"><img src="assets/ky.svg" width="160" alt="Ky the squirrel"></p>

<h1 align="center">Agent Ky</h1>

<p align="center"><b>A friendly squirrel that finds entry-level healthcare jobs with real patient-care hours, and writes a tailored resume for each one.</b></p>

Ky is built for someone working toward nursing school. It looks for jobs like CNA, patient care tech, ER tech, caregiver, medical assistant and phlebotomist near her ZIP code, ranks them by how much hands-on patient care they give, and writes an honest, ATS-friendly resume and cover letter for each one. Ky runs inside Claude, so there's nothing to install.

## Start here

**👉 Open [START_HERE.md](START_HERE.md)** and paste the message there into a new Claude chat. That's it.

Ky pops up as a little helper with three steps:

1. **Add your resume** (PDF, Word, or a photo of a paper resume)
2. **Type your ZIP code**
3. **Pick how many jobs** to find right now, then tap **Start the search**

You get a list of jobs near you, each with:

- **Patient-care hours** rating (how hands-on the job is) and **fit** rating (do you qualify)
- Badges like *Paid training*, *Tuition help*, *Flexible schedule*, and warnings like *Needs CNA license* or *Asks you to pay a fee*
- A **tailored resume** you can download as a PDF or Word file
- A **cover letter**, interview tips, and a note from Ky on why the job is worth it

## What else Ky does

- **Job alerts.** Ky can check every morning and send a notification when a new job shows up near you, with a resume already written.
- **Help applying.** Ky can fill in an application in Chrome for you. It warns you first that this uses a lot of Claude usage (applying yourself is usually faster), it never types passwords, and it stops before Submit so you press it yourself.
- **Honesty built in.** Ky only uses facts from your resume. A fact checker removes any job, certification, number or tool that isn't on your resume before you ever see it.

## How it's built

| Part | What it does |
|---|---|
| [`START_HERE.md`](START_HERE.md) | The one message she pastes into Claude |
| [`skills/ky/SKILL.md`](skills/ky/SKILL.md) | Ky's personality and instructions for Claude: setup, alerts, applying |
| [`skills/ky/ALERTS.md`](skills/ky/ALERTS.md) | What Ky does on each daily job check |
| [`skills/ky/APPLY.md`](skills/ky/APPLY.md) | How Ky helps apply, with the usage warning and safety rules |
| [`helper/ky.html`](helper/ky.html) | The squirrel helper page. It runs in her Claude: reads her resume, searches Indeed through her own Indeed connector, asks Claude to tailor each resume, fact-checks it, and makes the PDF and Word files |
| [`agent/`](agent) | Ky's system prompt and the tailoring, interview-prep and follow-up prompts |
| [`ky/`](ky) | A small Python engine used by the daily check: `ky score` ranks jobs, `ky check` fact-checks a resume, `ky search` can also use free job APIs (Adzuna, USAJOBS, Jooble) and hospital career sites |
| [`PROMPT.md`](PROMPT.md) | The original design brief |

### Privacy

Her resume, profile and jobs are stored only in her own private Ky page inside her Claude account. This repo is public and never holds personal data; `profile.yaml`, `data/`, `output/` and `.env` are git-ignored.

### Running the engine yourself (optional, for developers)

```bash
pip install -e ".[dev]"
pytest                                    # run the tests
ky score results.md --profile profile.example.yaml --limit 5
ky check tailored.json --profile profile.example.yaml
cp .env.example .env                      # add free job API keys, then:
ky search --zip 92501 --profile profile.example.yaml
```

To add a local hospital's job site, list it in `config/employers.yaml` (Workday and RSS are supported).

## License

MIT
