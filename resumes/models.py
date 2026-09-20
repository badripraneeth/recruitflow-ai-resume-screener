from django.db import models
from django.conf import settings


class Resume(models.Model):
    """
    Stores uploaded candidate resumes and extracted raw text.
    A Resume strictly belongs to a recruiter and is associated with a specific Job.
    Candidate name and email are optional at upload time (to be extracted in future phases).
    """
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='resumes',
        help_text="Recruiter who uploaded and owns this resume"
    )
    job = models.ForeignKey(
        'screener.Job',
        on_delete=models.CASCADE,
        related_name='resumes',
        null=True,
        blank=True,
        help_text="Job posting this resume was submitted for"
    )
    candidate_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional candidate name (extracted in subsequent phases)"
    )
    candidate_email = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional candidate email (extracted in subsequent phases)"
    )
    file = models.FileField(
        upload_to='resumes/%Y/%m/',
        help_text="Uploaded PDF resume file"
    )
    extracted_text = models.TextField(
        blank=True,
        help_text="Raw text extracted from the PDF via pypdf"
    )
    STATUS_REVIEW = 'review'
    STATUS_SHORTLISTED = 'shortlisted'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_REVIEW, 'In Review'),
        (STATUS_SHORTLISTED, 'Shortlisted'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_REVIEW,
        help_text="Recruiter review status. Every newly screened resume starts strictly as 'review'."
    )
    recruiter_notes = models.TextField(
        blank=True,
        default='',
        help_text="Notes written by recruiter"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Resume'
        verbose_name_plural = 'Resumes'

    def __str__(self):
        target = self.candidate_name or self.file.name.split('/')[-1]
        job_title = f" ({self.job.title})" if self.job else ""
        return f"{target}{job_title} - Recruiter: {self.recruiter.email}"

    @property
    def filename(self):
        return self.file.name.split('/')[-1].split('\\')[-1]
