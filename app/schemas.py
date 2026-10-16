from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SERVER_COMPUTED = "Computed by the server; always output null"


class Model(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _null_means_default(cls, data: Any) -> Any:
        """LLMs sometimes emit null for absent values; use the field default ("" / [] / null) instead."""
        return {k: v for k, v in data.items() if v is not None} if isinstance(data, dict) else data


class YearMonth(Model):
    year: int | None = None
    month: int | None = None


class DateOfBirth(Model):
    year: int | None = None
    month: int | None = None
    day: int | None = None


class Basics(Model):
    first_name: str = ""
    last_name: str = ""
    gender: Literal["male", "female", "other"] | None = Field(
        None, description="Only if explicitly stated in the CV; never infer from names or photos"
    )
    emails: list[str] = []
    urls: list[str] = Field([], description="Profile and portfolio URLs, e.g. linkedin.com/in/jane")
    phone_numbers: list[str] = []
    date_of_birth: DateOfBirth = Field(default_factory=DateOfBirth, description="Only if explicitly stated in the CV")
    address: str = Field("", description="Postal address or location as written in the CV")
    total_experience_in_years: int | None = Field(None, description=SERVER_COMPUTED)
    profession: str = Field("", description="Current or target job title, e.g. 'AI Software Engineer'")
    summary: str = Field("", description="The candidate's own summary, verbatim")
    skills: list[str] = Field([], description="Short, deduplicated skill names, e.g. 'Python', 'Kubernetes'")
    has_driving_license: bool = Field(False, description="True only if the CV mentions a driving license")


class Language(Model):
    name: str = Field("", description="English name of the language, e.g. 'French'")
    iso_code: str = Field("", description="ISO 639-1 code, e.g. 'fr'")
    fluency: int | None = Field(None, description="1 = elementary, 3 = professional, 5 = native or bilingual")


class Education(Model):
    start_year: int | None = None
    is_current: bool = False
    end_year: int | None = None
    issuing_organization: str = Field("", description="School or university")
    description: str = Field("", description="Degree and field of study, e.g. 'Master in Computer Science'")


class Certification(Model):
    year: int | None = None
    issuing_organization: str = ""
    description: str = Field("", description="Name of the training or certification")


class ProfessionalExperience(Model):
    start_date: YearMonth = Field(default_factory=YearMonth)
    is_current: bool = False
    end_date: YearMonth = Field(default_factory=YearMonth, description="Leave year and month null for a current role")
    duration_in_months: int | None = Field(None, description=SERVER_COMPUTED)
    company: str = ""
    location: str = ""
    title: str = ""
    description: str = Field("", description="Responsibilities and achievements, one per line")


class Award(Model):
    year: int | None = None
    title: str = ""
    description: str = ""


class Reference(Model):
    full_name: str = ""
    phone_number: str = ""
    email: str = ""
    company: str = ""
    position: str = ""
    description: str = ""


class Profile(Model):
    basics: Basics = Field(default_factory=Basics)
    languages: list[Language] = Field([], description="Spoken languages, not programming languages")
    educations: list[Education] = []
    trainings_and_certifications: list[Certification] = []
    professional_experiences: list[ProfessionalExperience] = Field([], description="Most recent first")
    awards: list[Award] = []
    references: list[Reference] = []


class Extraction(Model):
    """What the LLM fills in. Field descriptions double as extraction instructions."""

    is_resume: bool = Field(description="True only if the document is a resume or CV")
    cv_language: str = Field("", description="ISO 639-1 code of the language the CV is written in")
    profile: Profile = Field(default_factory=Profile)


class ParseResponse(BaseModel):
    profile: Profile
    cv_language: str = Field(description="ISO 639-1 code of the language the CV is written in")
    cv_text: str = Field(description="Full plain text extracted from the CV")


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    request_id: str | None
    error: ErrorDetail
