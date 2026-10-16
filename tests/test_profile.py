from datetime import date

from app.schemas import ProfessionalExperience, Profile, YearMonth
from app.services.profile import finalize_profile, total_experience_months

TODAY = date(2026, 10, 16)


def ym(value: str | None) -> YearMonth:
    if not value:
        return YearMonth()
    year, _, month = value.partition("-")
    return YearMonth(year=int(year), month=int(month) if month else None)


def job(start: str | None, end: str | None = None, current: bool = False) -> ProfessionalExperience:
    return ProfessionalExperience(company="X", start_date=ym(start), end_date=ym(end), is_current=current)


def test_single_role_counts_both_end_months():
    assert total_experience_months([job("2020-01", "2020-12")], TODAY) == 12


def test_overlapping_roles_are_not_double_counted():
    assert total_experience_months([job("2020-01", "2020-12"), job("2020-06", "2021-06")], TODAY) == 18


def test_gaps_between_roles_are_excluded():
    assert total_experience_months([job("2019-01", "2019-06"), job("2020-01", "2020-06")], TODAY) == 12


def test_year_only_dates_span_full_years():
    assert total_experience_months([job("2014", "2015")], TODAY) == 24


def test_unusable_dates_are_ignored():
    jobs = [job(None, "2020-01"), job("2021-05", "2020-01"), job("2030-01", current=True)]
    jobs.append(ProfessionalExperience(start_date=YearMonth(year=2020, month=13), end_date=ym("2021-01")))
    assert total_experience_months(jobs, TODAY) == 0


def test_finalize_fills_server_owned_fields():
    profile = Profile(professional_experiences=[job("2024-11", current=True), job("2014-08", "2019-09"), job(None)])
    profile.basics.urls = ["https://www.LinkedIn.com/in/jane/", "linkedin.com/in/jane", "jane@example.com"]

    finalize_profile(profile, "", ["https://github.com/jane", "medium.com/@jane"], TODAY)

    current, past, undated = profile.professional_experiences
    assert current.end_date == YearMonth(year=2026, month=10) and current.duration_in_months == 24
    assert past.duration_in_months == 62
    assert undated.duration_in_months is None
    assert profile.basics.total_experience_in_years == 7
    assert profile.basics.urls == ["github.com/jane", "linkedin.com/in/jane", "medium.com/@jane"]


def test_names_are_snapped_to_spelling_in_cv():
    profile = Profile()
    profile.basics.first_name, profile.basics.last_name = "YASH", "NALVADE"
    finalize_profile(profile, "YASH NALAVADE\nPune, India\nYash Nalavade, 2026", [], TODAY)
    assert (profile.basics.first_name, profile.basics.last_name) == ("YASH", "NALAVADE")


def test_names_without_a_close_match_are_kept():
    profile = Profile()
    profile.basics.first_name, profile.basics.last_name = "Jean", "Dujardin"
    finalize_profile(profile, "Curriculum vitae of J. Dupont", [], TODAY)
    assert (profile.basics.first_name, profile.basics.last_name) == ("Jean", "Dujardin")
