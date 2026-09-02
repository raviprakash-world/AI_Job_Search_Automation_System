from datetime import date
from pathlib import Path

from docx import Document

from app.schemas.resumes import (
    ResumeCertificationOut,
    ResumeEducationOut,
    ResumeExperienceOut,
    ResumeProjectOut,
    StructuredResumeContent,
)
from app.services.document_parsing import parse_docx
from app.services.resume_rendering_service import render_resume_docx


def _content() -> StructuredResumeContent:
    return StructuredResumeContent(
        full_name="Jane Doe",
        phone="555-1234",
        email="jane@example.com",
        location="Remote",
        links={"github": "https://github.com/jane"},
        professional_summary="Experienced backend engineer focused on reliability.",
        skills=["Python", "PostgreSQL"],
        experiences=[
            ResumeExperienceOut(
                experience_id="exp-1",
                company="Acme Corp",
                title="Senior Engineer",
                location="Remote",
                start_date=date(2020, 1, 1),
                end_date=date(2023, 1, 1),
                is_current=False,
                bullets=["Led backend team of 5 engineers", "Reduced latency by 30%"],
            )
        ],
        education=[ResumeEducationOut(institution="State University", degree="B.S. Computer Science")],
        projects=[ResumeProjectOut(name="Side Project", description="A thing I built", technologies=["Python"])],
        certifications=[ResumeCertificationOut(name="AWS SAA", issuer="AWS")],
    )


def test_render_produces_a_readable_docx(tmp_path: Path):
    destination = tmp_path / "resume.docx"
    render_resume_docx(_content(), destination)

    assert destination.exists()
    text = parse_docx(destination)

    assert "Jane Doe" in text
    assert "jane@example.com" in text
    assert "555-1234" in text
    assert "Senior Engineer — Acme Corp" in text
    assert "Led backend team of 5 engineers" in text
    assert "Reduced latency by 30%" in text
    assert "State University" in text
    assert "AWS SAA" in text
    assert "Side Project" in text


def test_render_uses_no_tables(tmp_path: Path):
    # ATS-safety guarantee: the renderer must never construct a table.
    destination = tmp_path / "resume.docx"
    render_resume_docx(_content(), destination)
    doc = Document(str(destination))
    assert doc.tables == []


def test_render_creates_parent_directories(tmp_path: Path):
    nested = tmp_path / "nested" / "dir" / "resume.docx"
    render_resume_docx(_content(), nested)
    assert nested.exists()


def test_render_omits_empty_sections(tmp_path: Path):
    content = _content()
    content.projects = []
    content.certifications = []
    destination = tmp_path / "resume.docx"
    render_resume_docx(content, destination)
    text = parse_docx(destination)
    assert "Projects" not in text
    assert "Certifications" not in text
