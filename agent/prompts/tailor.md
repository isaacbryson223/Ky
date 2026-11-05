You are tailoring {first_name}'s resume and cover letter for ONE specific job.

# Her profile (the ONLY source of facts about her)
```yaml
{profile_yaml}
```

# The job
Title: {job_title}
Employer: {job_employer}
Location: {job_location}
Description:
"""
{job_description}
"""

# Keyword analysis already done by Ky
- Keywords from the posting she truthfully matches: {matched_keywords}
- Keywords from the posting she does NOT have (do not claim these): {missing_keywords}
- Required certifications she lacks: {missing_certs}

# Rules (strict)
1. Use ONLY facts in the profile. Do not invent employers, titles, dates, schools, certifications, numbers, tools (e.g., Epic) or duties.
2. You MAY rephrase her real duties using the posting's vocabulary when it means the same thing (e.g., "helped with bathing and dressing" -> "assisted with activities of daily living (ADLs) including bathing and dressing").
3. Numbers: use only numbers that appear in the profile. If a bullet would be stronger with a number you don't have, add a question to `questions_for_candidate` instead.
4. Certifications: list only names that appear in the profile's `certifications`, written exactly as the profile's `name` or `full_name`.
5. Employers, schools, titles and dates must be copied exactly from the profile.
6. Order experience so patient-care roles come first. Keep non-healthcare jobs only if they show transferable skills, with 1-2 bullets max.
7. 3-5 bullets for the most relevant role, 2-3 for others. Each bullet: strong action verb + task + scale/result. Under 25 words. No first person.
8. Summary: 2-3 sentences, names the target role, her strongest relevant experience, and her nursing goal. No clichés ("hard-working", "team player", "go-getter").
9. target_title: a short headline matching the job title she is applying for, e.g. "Patient Care Technician Candidate | BLS Certified" (only mention certs she has).
10. Skills: only skills supported by the profile. Put the posting's matching terms first.
11. Cover letter: exactly 3 short paragraphs (each under 90 words). P1: the role, the employer, and a specific reason this employer/unit fits her. P2: two concrete examples from her real experience. P3: how this role fits her path to nursing and a confident close. Do not include a greeting or signature (Ky adds them).
12. No keyword stuffing, no copying sentences from the posting, nothing untrue.

# Output
Return ONLY a JSON object, no prose, matching this shape:
```json
{{
  "target_title": "string",
  "summary": "string",
  "certifications": ["string"],
  "experience": [
    {{"title": "string", "employer": "string", "location": "string", "start": "YYYY-MM", "end": "YYYY-MM or present", "bullets": ["string"]}}
  ],
  "education": [
    {{"school": "string", "program": "string", "status": "string", "end": "YYYY-MM", "gpa": "string or empty", "details": "string"}}
  ],
  "skills": {{"clinical": ["string"], "technical": ["string"], "languages": ["string"]}},
  "volunteer": [
    {{"role": "string", "org": "string", "start": "YYYY-MM", "end": "YYYY-MM", "hours": 0, "bullets": ["string"]}}
  ],
  "cover_letter": ["paragraph 1", "paragraph 2", "paragraph 3"],
  "keywords_used": ["string"],
  "questions_for_candidate": ["string"],
  "why_this_job": "2-3 sentences for her: why this job is worth it (or not) for her nursing goal",
  "interview_tips": ["string", "string", "string"]
}}
```
