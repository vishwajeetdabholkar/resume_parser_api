import difflib
import re
from datetime import date

from app.schemas import ProfessionalExperience, Profile, YearMonth
from app.services.pdf import normalize_links

WORD_RE = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")


def _month_index(value: YearMonth, *, is_end: bool) -> int | None:
    """Absolute month number. A missing month means January for a start date and December for an end date."""
    if not value.year:
        return None
    month = value.month or (12 if is_end else 1)
    return value.year * 12 + month - 1 if 1 <= month <= 12 else None


def _span(job: ProfessionalExperience, now: int) -> tuple[int, int] | None:
    start = _month_index(job.start_date, is_end=False)
    end = now if job.is_current else _month_index(job.end_date, is_end=True)
    if start is None or end is None or start > min(end, now):
        return None
    return start, min(end, now)


def total_experience_months(jobs: list[ProfessionalExperience], today: date) -> int:
    """Total months worked, counting each month once even when roles overlap."""
    now = today.year * 12 + today.month - 1
    total, current = 0, None
    for start, end in sorted(span for job in jobs if (span := _span(job, now))):
        if current and start <= current[1]:
            current = (current[0], max(current[1], end))
            continue
        if current:
            total += current[1] - current[0] + 1
        current = (start, end)
    if current:
        total += current[1] - current[0] + 1
    return total


def _snap_to_text(value: str, words: dict[str, str]) -> str:
    """Correct small LLM transcription slips (e.g. a dropped letter) using the closest word in the CV."""
    fixed = []
    for token in value.split():
        if token.lower() not in words:
            close = difflib.get_close_matches(token.lower(), words, n=1, cutoff=0.8)
            token = words[close[0]] if close else token
        fixed.append(token)
    return " ".join(fixed)


def finalize_profile(profile: Profile, cv_text: str, pdf_links: list[str], today: date | None = None) -> Profile:
    """Fill the fields the server owns: durations, total experience, current end dates and URLs."""
    words: dict[str, str] = {}
    for word in WORD_RE.findall(cv_text):
        words.setdefault(word.lower(), word)
    profile.basics.first_name = _snap_to_text(profile.basics.first_name, words)
    profile.basics.last_name = _snap_to_text(profile.basics.last_name, words)

    today = today or date.today()
    now = today.year * 12 + today.month - 1
    for job in profile.professional_experiences:
        if job.is_current:
            job.end_date = YearMonth(year=today.year, month=today.month)
        span = _span(job, now)
        job.duration_in_months = span[1] - span[0] + 1 if span else None

    basics = profile.basics
    basics.total_experience_in_years = total_experience_months(profile.professional_experiences, today) // 12
    basics.urls = normalize_links([*basics.urls, *pdf_links])
    return profile
