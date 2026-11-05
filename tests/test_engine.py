import json
from datetime import date
from pathlib import Path

import pytest

from ky import factguard
from ky.cli import main
from ky.dedupe import dedupe
from ky.models import Job
from ky.profile import Profile
from ky.score import classify, cert_requirements, rank, score_job
from ky.sources.base import parse_pay
from ky.sources.indeed import parse_details, parse_search

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 5)


@pytest.fixture
def profile():
    return Profile.load(ROOT / "profile.example.yaml")


def test_parse_indeed_search():
    jobs = parse_search((FIX / "indeed_search.md").read_text())
    assert len(jobs) == 5
    j = jobs[0]
    assert j.title.startswith("Patient Care Technician")
    assert j.employer == "Example Valley Hospital"
    assert j.posted == "2026-11-03"
    assert (j.pay_min, j.pay_max, j.pay_period) == (22, 26, "hour")
    assert j.external_id == "JOBSEARCH_900001"


def test_parse_indeed_details():
    j = parse_details((FIX / "indeed_details.md").read_text())
    assert j.title == "Certified Nursing Assistant - Nights"
    assert "CNA license required" in j.description
    assert "**Company:**" not in j.description


def test_dedupe_merges_same_job():
    jobs = parse_search((FIX / "indeed_search.md").read_text())
    assert len(dedupe(jobs)) == 4


@pytest.mark.parametrize("title,tier", [
    ("Patient Care Technician - ED", "A"),
    ("CNA - PM - FT", "A"),
    ("Caregiver - In-Home Care", "A"),
    ("Phlebotomist II", "B"),
    ("Medication Technician / Caregiver", "A"),
    ("Medical Scribe", "C"),
    ("Registered Nurse - ICU", ""),
    ("Medical Assistant Instructor", ""),
    ("Nurse Manager", ""),
])
def test_classify(title, tier):
    assert classify(title)[0] == tier


def test_cert_requirements():
    req = cert_requirements("Active state CNA license required.\nBLS preferred.\nWill train for phlebotomy certification.")
    assert req["CNA"] == "required"
    assert req["BLS"] == "preferred"
    assert req["CPT"] == "preferred"


def test_scoring_prefers_hospital_and_flags_missing_cert(profile):
    search = parse_search((FIX / "indeed_search.md").read_text())
    pct = score_job(search[0], profile, TODAY)
    cna = score_job(parse_details((FIX / "indeed_details.md").read_text()), profile, TODAY)
    assert pct.clinical_score >= 75 and cna.clinical_score >= 75  # both hands-on roles
    assert "missing required CNA" in cna.reasons["fit"]
    assert "Tuition help" in cna.badges
    assert pct.fit_score > cna.fit_score  # she lacks the required CNA


def test_rank_drops_non_targets(profile):
    jobs = [score_job(j, profile, TODAY) for j in dedupe(parse_search((FIX / "indeed_search.md").read_text()))]
    titles = [j.title for j in rank(jobs)]
    assert not any("Instructor" in t or "Registered Nurse" in t for t in titles)
    assert titles[0].startswith("Patient Care Technician")


def test_red_flags(profile):
    j = Job(title="Nursing Assistant", employer="Confidential", location="", url="",
            description="Pay a $150 training fee. Send your SSN and bank account to start.", source="x")
    score_job(j, profile, TODAY)
    assert "Asks you to pay for training/application" in j.red_flags
    assert "Asks for SSN/bank info early" in j.red_flags
    assert "Employer not named" in j.red_flags


def test_parse_pay():
    assert parse_pay("$18.50 - $21 an hour") == (18.5, 21.0, "hour")
    assert parse_pay("$45k - $52k a year")[2] == "year"
    assert parse_pay("no pay listed") == (None, None, "")


def test_profile_certs(profile):
    assert profile.cert_codes(TODAY) == {"BLS"}
    assert profile.cert_codes(date(2029, 1, 1)) == set()  # expired


def _good_resume():
    return {
        "certifications": ["Basic Life Support (BLS) for Healthcare Providers"],
        "summary": "Pre-nursing student with home care experience.",
        "experience": [{
            "title": "Caregiver", "employer": "Sunrise Home Care", "start": "2025-03", "end": "present",
            "bullets": ["Assisted 4 clients per week with activities of daily living (ADLs)"],
        }],
        "education": [{"school": "Riverside City College", "gpa": "3.6"}],
        "volunteer": [{"role": "Hospital Volunteer", "org": "Riverside Community Hospital", "hours": 60, "bullets": []}],
        "skills": {"clinical": ["Vital signs"], "technical": [], "languages": ["Spanish (fluent)"]},
    }


def test_factguard_passes_truthful_resume(profile):
    assert factguard.check(_good_resume(), profile).ok


def test_factguard_blocks_invented_facts(profile):
    r = _good_resume()
    r["certifications"].append("CNA")
    r["experience"][0]["bullets"].append("Cared for 25 patients per shift using Epic")
    r["experience"].append({"title": "PCT", "employer": "Made Up Hospital", "bullets": []})
    r["education"][0]["gpa"] = "4.0"
    fixed, rep = factguard.clean(r, profile)
    assert not rep.ok
    assert fixed["certifications"] == ["Basic Life Support (BLS) for Healthcare Providers"]
    assert len(fixed["experience"]) == 1
    assert len(fixed["experience"][0]["bullets"]) == 1
    assert fixed["education"][0]["gpa"] == ""


def test_cli_score(tmp_path, capsys):
    rc = main(["score", str(FIX / "indeed_search.md"), str(FIX / "indeed_details.md"),
               "--profile", str(ROOT / "profile.example.yaml"), "--limit", "3"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and 1 <= len(out) <= 3
    assert all(j["tier"] for j in out)


def test_page_key_matches_helper_page():
    # value computed by the helper page's JavaScript hash for the same job
    from ky.models import page_key
    assert page_key("Example Valley Hospital", "Patient Care Technician - ED (Nights)", "Riverside, CA") == "j1798gmy"


def test_missing_certs_listed(profile):
    cna = score_job(parse_details((FIX / "indeed_details.md").read_text()), profile, TODAY)
    assert cna.missing == ["CNA license"]
    assert cna.to_dict()["key"].startswith("j")


def test_ats_report_matches_page_logic():
    from ky.ats import ats_report
    job = parse_details((FIX / "indeed_details.md").read_text())
    rep = ats_report(job.title, job.description, _good_resume())
    assert "activities of daily living (ADLs)" in rep["matched"]
    assert "vital signs" in rep["matched"]
    assert rep["total"] == len(rep["matched"]) + len(rep["missing"])
    assert 0 <= rep["pct"] <= 100


def test_terms_and_shifts(capsys, profile):
    assert main(["terms", "--roles", "cna,er"]) == 0
    assert json.loads(capsys.readouterr().out) == ["certified nursing assistant", "nursing assistant hospital", "emergency room technician"]
    rc = main(["score", str(FIX / "indeed_details.md"), "--profile", str(ROOT / "profile.example.yaml"), "--shifts", "days"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and "may clash" in out[0]["reasons"]["fit"]


def test_helper_page_lists_match_engine():
    """The helper page and the engine must use the same job types and ATS keywords."""
    import re
    from ky.vocab import ATS_KEYWORDS, ROLE_OPTIONS
    page = (ROOT / "helper" / "ky.html").read_text()
    for rid, label, terms, on in ROLE_OPTIONS:
        assert f'["{rid}", "{label}", {json.dumps(terms)}, {"true" if on else "false"}]' in page.replace(", ", ", ")
    page_kws = re.findall(r'^\s+"([^"]+)": \[', page.split("const ATS_KEYWORDS = {")[1].split("};")[0], re.M)
    assert page_kws == list(ATS_KEYWORDS)


def test_factguard_accepts_her_own_answers(profile):
    r = _good_resume()
    r["experience"][0]["bullets"].append("Worked 32 hours per week supporting clients")
    assert not factguard.check(r, profile).ok  # 32 isn't in her profile yet
    profile.data["extra_facts"] = [{"question": "About how many hours a week do you work?", "answer": "About 32 hours a week"}]
    assert factguard.check(r, profile).ok


def test_cert_matching_is_whole_word(profile):
    assert "PALS" not in cert_requirements("Experience with cerebral palsy patients preferred.")
    assert "CNA" not in cert_requirements("You will work alongside CNAs and nurses.")
    r = _good_resume()
    r["experience"][0]["bullets"].append("Supported a client with cerebral palsy during daily routines")
    assert factguard.check(r, profile).ok


def test_score_accepts_web_jobs_json(tmp_path, capsys):
    jobs = [{"title": "Patient Care Technician", "employer": "Example Valley Hospital", "location": "Riverside, CA",
             "url": "https://example.com/careers/1", "description": "Hospital PCT. Take vital signs, assist with ADLs. BLS required.",
             "posted": "2026-11-03", "pay": "$22 - $26 an hour", "source": "Web", "via": "Example Valley Hospital careers"}]
    f = tmp_path / "jobs.json"; f.write_text(json.dumps(jobs))
    assert main(["score", str(f), "--profile", str(ROOT / "profile.example.yaml")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["via"] == "Example Valley Hospital careers" and out[0]["pay_min"] == 22 and out[0]["tier"] == "A"
