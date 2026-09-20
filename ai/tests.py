from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from screener.models import Job, ScreeningResult
from resumes.models import Resume
from .resume_analysis import validate_resume_text, clean_resume_text, EmptyResumeTextError
from .job_analysis import prepare_job_context
from .llm_service import clean_json_response, LLMService, LLMJSONDecodeError
from .matching import (
    validate_analysis_schema,
    analyze_resume_against_job,
    AnalysisValidationError
)

User = get_user_model()


class MockLLMService(LLMService):
    """Deterministic Mock LLM service for testing."""
    def __init__(self, mock_data=None):
        super().__init__(api_key="mock-key")
        self.mock_data = mock_data or {
            "candidate_name": "Rahul Kumar",
            "candidate_email": "rahul@example.com",
            "skills": ["Python", "Django", "PostgreSQL", "Git"],
            "experience_years": 2.5,
            "education": [
                {
                    "degree": "B.Tech",
                    "field": "Computer Science"
                }
            ],
            "projects": [
                {
                    "name": "E-commerce Platform",
                    "description": "Django based web application"
                }
            ],
            "matched_required_skills": ["Python", "Django"],
            "missing_required_skills": ["Docker"],
            "matched_preferred_skills": ["PostgreSQL"],
            "missing_preferred_skills": ["AWS"],
            "ai_summary": "Strong backend candidate with practical Django experience."
        }

    def generate_json(self, system_prompt, user_prompt, timeout=60):
        return self.mock_data


class AIPreProcessingTests(TestCase):
    def test_empty_resume_text_raises_error(self):
        with self.assertRaises(EmptyResumeTextError):
            validate_resume_text("")
        with self.assertRaises(EmptyResumeTextError):
            validate_resume_text("   \n\n\t  ")

    def test_short_resume_text_raises_error(self):
        with self.assertRaises(EmptyResumeTextError):
            validate_resume_text("Too short")

    def test_clean_resume_text(self):
        raw = "Hello\x00World\r\n\r\n\r\n\r\nThis is a    test  line."
        cleaned = clean_resume_text(raw)
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn("\r", cleaned)
        self.assertIn("Hello World", cleaned)


class LLMServiceUtilityTests(TestCase):
    def test_clean_json_response_strips_markdown_fences(self):
        fenced_json = '```json\n{"name": "Alice", "score": 90}\n```'
        cleaned = clean_json_response(fenced_json)
        self.assertEqual(cleaned, '{"name": "Alice", "score": 90}')

    def test_clean_json_response_plain_backticks(self):
        fenced = '```\n{"title": "Dev"}\n```'
        cleaned = clean_json_response(fenced)
        self.assertEqual(cleaned, '{"title": "Dev"}')


class MatchingSchemaValidationTests(TestCase):
    def test_schema_validation_strips_forbidden_score_fields(self):
        """
        Specification requirement:
        The LLM MUST NOT generate the final 0-100 score.
        Validate that schema enforcement removes any hallucinated score keys.
        """
        hallucinated_data = {
            "candidate_name": "John Doe",
            "candidate_email": "john@example.com",
            "skills": ["Python"],
            "experience_years": 4,
            "education": [{"degree": "B.S.", "field": "CS"}],
            "projects": [{"name": "P1", "description": "D1"}],
            "matched_required_skills": ["Python"],
            "missing_required_skills": [],
            "matched_preferred_skills": [],
            "missing_preferred_skills": [],
            "ai_summary": "Good fit",
            "score": 88,
            "total_score": 88.5,
            "rating": "A+"
        }
        validated = validate_analysis_schema(hallucinated_data)
        self.assertNotIn("score", validated)
        self.assertNotIn("total_score", validated)
        self.assertNotIn("rating", validated)
        self.assertEqual(validated["candidate_name"], "John Doe")
        self.assertEqual(validated["experience_years"], 4.0)

    def test_schema_validation_handles_missing_fields_gracefully(self):
        minimal_data = {
            "candidate_name": "Jane",
        }
        validated = validate_analysis_schema(minimal_data)
        self.assertEqual(validated["candidate_name"], "Jane")
        self.assertEqual(validated["candidate_email"], "")
        self.assertEqual(validated["skills"], [])
        self.assertEqual(validated["experience_years"], 0.0)
        self.assertEqual(validated["education"], [])
        self.assertEqual(validated["projects"], [])

    def test_schema_validation_rejects_non_dict(self):
        with self.assertRaises(AnalysisValidationError):
            validate_analysis_schema(["not", "a", "dict"])


class EndToEndAnalysisIntegrationTests(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user(
            email='recruiter@company.com',
            password='Password123!'
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title="Senior Django Developer",
            description="Looking for an experienced Django engineer.",
            required_skills=["Python", "Django", "Docker"],
            preferred_skills=["PostgreSQL", "AWS"],
            min_experience=2.0
        )
        dummy_file = SimpleUploadedFile("sample_resume.pdf", b"%PDF-1.4 dummy", content_type="application/pdf")
        self.resume = Resume.objects.create(
            recruiter=self.recruiter,
            job=self.job,
            file=dummy_file,
            extracted_text="Rahul Kumar - Software Engineer\nEmail: rahul@example.com\nPython, Django, PostgreSQL\nExperience: 2.5 years at TechCorp"
        )

    def test_analyze_resume_against_job_updates_models(self):
        mock_service = MockLLMService()
        screening_result, analysis = analyze_resume_against_job(
            resume=self.resume,
            job=self.job,
            llm_service=mock_service
        )

        # 1. Verify Resume is updated with candidate name and email
        self.resume.refresh_from_db()
        self.assertEqual(self.resume.candidate_name, "Rahul Kumar")
        self.assertEqual(self.resume.candidate_email, "rahul@example.com")

        # 2. Verify ScreeningResult was created and linked
        self.assertEqual(screening_result.job, self.job)
        self.assertEqual(screening_result.resume, self.resume)
        self.assertEqual(screening_result.matched_required_skills, ["Python", "Django"])
        self.assertEqual(screening_result.missing_required_skills, ["Docker"])
        self.assertEqual(screening_result.candidate_experience_years, 2.5)
        self.assertEqual(screening_result.candidate_summary, "Strong backend candidate with practical Django experience.")

        # 3. Specification rule: Score MUST NOT be generated by LLM / remains 0.0
        self.assertEqual(screening_result.total_score, 0.0)
        self.assertEqual(screening_result.required_skills_score, 0.0)

    def test_analyze_empty_resume_raises_error(self):
        self.resume.extracted_text = "   "
        self.resume.save()
        with self.assertRaises(EmptyResumeTextError):
            analyze_resume_against_job(self.resume, self.job)
