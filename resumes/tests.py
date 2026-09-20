import io
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from pypdf import PdfWriter
from screener.models import Job
from .models import Resume
from .services.pdf_parser import (
    extract_text_from_pdf,
    validate_pdf_file,
    PDFValidationError,
    PDFParsingError
)

User = get_user_model()


def create_sample_pdf_bytes(text="Sample candidate resume content."):
    """Helper to generate a real, valid PDF in-memory with pypdf."""
    # Since pypdf's PdfWriter creates valid PDF structure with metadata/pages
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


class PDFParserServiceTests(TestCase):
    def test_rejects_non_pdf_extension(self):
        fake_file = SimpleUploadedFile("resume.docx", b"dummy content", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        with self.assertRaises(PDFValidationError) as ctx:
            extract_text_from_pdf(fake_file)
        self.assertIn("Only PDF files are supported", str(ctx.exception))

    def test_rejects_invalid_pdf_header(self):
        fake_file = SimpleUploadedFile("malicious.pdf", b"NOT_A_REAL_PDF_HEADER", content_type="application/pdf")
        with self.assertRaises(PDFValidationError) as ctx:
            extract_text_from_pdf(fake_file)
        self.assertIn("valid PDF header", str(ctx.exception))

    def test_rejects_oversized_file(self):
        # Create small payload but mock size attribute
        fake_file = SimpleUploadedFile("huge.pdf", b"%PDF-1.4 header", content_type="application/pdf")
        fake_file.size = 11 * 1024 * 1024  # 11MB
        with self.assertRaises(PDFValidationError) as ctx:
            extract_text_from_pdf(fake_file)
        self.assertIn("exceeds the maximum allowed size", str(ctx.exception))

    def test_handles_corrupted_pdf_stream(self):
        corrupted_bytes = b"%PDF-1.4\n%corrupted stream content that is unparsable by pypdf %%EOF"
        corrupted_file = SimpleUploadedFile("corrupt.pdf", corrupted_bytes, content_type="application/pdf")
        with self.assertRaises(PDFParsingError):
            extract_text_from_pdf(corrupted_file)

    def test_extracts_from_valid_pdf(self):
        pdf_bytes = create_sample_pdf_bytes()
        valid_file = SimpleUploadedFile("sample.pdf", pdf_bytes, content_type="application/pdf")
        # Blank page created with PdfWriter extracts to empty or whitespace string without error
        text = extract_text_from_pdf(valid_file)
        self.assertIsInstance(text, str)


class ResumeUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.recruiter_a = User.objects.create_user(
            email='recruiter_a@test.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='A'
        )
        self.recruiter_b = User.objects.create_user(
            email='recruiter_b@test.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='B'
        )

        self.job_a = Job.objects.create(
            recruiter=self.recruiter_a,
            title="Backend Python Engineer",
            description="Django experience required.",
            required_skills=["Python", "Django"],
            min_experience=3.0
        )
        self.job_b = Job.objects.create(
            recruiter=self.recruiter_b,
            title="UI/UX Designer",
            description="Figma experience.",
            required_skills=["Figma"],
            min_experience=2.0
        )

    def test_recruiter_can_upload_multiple_resumes_for_own_job(self):
        """Test uploading multiple valid PDFs for Recruiter A's job."""
        self.client.login(email='recruiter_a@test.com', password='Password123!')
        
        pdf1 = SimpleUploadedFile("resume_alice.pdf", create_sample_pdf_bytes(), content_type="application/pdf")
        pdf2 = SimpleUploadedFile("resume_bob.pdf", create_sample_pdf_bytes(), content_type="application/pdf")

        response = self.client.post(
            reverse('resume_upload'),
            {
                'job_id': self.job_a.pk,
                'resumes': [pdf1, pdf2]
            },
            follow=True
        )

        # Redirects to job detail page
        self.assertRedirects(response, reverse('job_detail', kwargs={'pk': self.job_a.pk}))
        # Verify 2 resumes created for job_a
        self.assertEqual(Resume.objects.filter(job=self.job_a).count(), 2)
        resumes = Resume.objects.filter(job=self.job_a)
        for res in resumes:
            self.assertEqual(res.recruiter, self.recruiter_a)
            self.assertIsNotNone(res.extracted_text)

    def test_recruiter_cannot_upload_resumes_into_another_recruiters_job(self):
        """
        Specification requirement:
        A recruiter must never upload resumes into another recruiter's job.
        Enforce recruiter ownership (returns 404).
        """
        self.client.login(email='recruiter_b@test.com', password='Password123!')
        pdf = SimpleUploadedFile("intruder_resume.pdf", create_sample_pdf_bytes(), content_type="application/pdf")

        # Recruiter B attempts to upload to Job A (owned by Recruiter A)
        response = self.client.post(
            reverse('resume_upload'),
            {
                'job_id': self.job_a.pk,
                'resumes': [pdf]
            }
        )

        self.assertEqual(response.status_code, 404)
        # Ensure no resumes were created for Job A
        self.assertEqual(Resume.objects.filter(job=self.job_a).count(), 0)

    def test_upload_get_only_shows_own_jobs(self):
        """Upload page dropdown only displays the logged-in recruiter's jobs."""
        self.client.login(email='recruiter_a@test.com', password='Password123!')
        response = self.client.get(reverse('resume_upload'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Backend Python Engineer')
        self.assertNotContains(response, 'UI/UX Designer')

    def test_job_detail_has_upload_resumes_button(self):
        """Job detail page displays the 'Upload Resumes' button."""
        self.client.login(email='recruiter_a@test.com', password='Password123!')
        response = self.client.get(reverse('job_detail', kwargs={'pk': self.job_a.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Upload Resumes')

    def test_recruiter_cannot_analyze_another_recruiters_resume(self):
        """Recruiter B cannot analyze Recruiter A's resume (returns 404)."""
        resume_a = Resume.objects.create(
            recruiter=self.recruiter_a,
            job=self.job_a,
            file=SimpleUploadedFile("alice.pdf", create_sample_pdf_bytes()),
            extracted_text="Alice Johnson Python Django 3 years experience"
        )
        self.client.login(email='recruiter_b@test.com', password='Password123!')
        response = self.client.post(reverse('resume_analyze', kwargs={'pk': resume_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_resume_analysis_detail_view_isolation(self):
        """Recruiter B cannot view Recruiter A's resume analysis (returns 404)."""
        resume_a = Resume.objects.create(
            recruiter=self.recruiter_a,
            job=self.job_a,
            file=SimpleUploadedFile("alice.pdf", create_sample_pdf_bytes()),
            extracted_text="Alice Johnson Python Django 3 years experience"
        )
        self.client.login(email='recruiter_b@test.com', password='Password123!')
        response = self.client.get(reverse('resume_analysis_detail', kwargs={'pk': resume_a.pk}))
        self.assertEqual(response.status_code, 404)
