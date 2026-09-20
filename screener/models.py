from django.db import models
from django.conf import settings


class Job(models.Model):
    """
    Stores recruiter-managed job postings.
    Recruiters own jobs and cannot access other recruiters' jobs.
    minimum_score and shortlist_count are explicitly optional (nullable).
    """
    STATUS_ACTIVE = 'active'
    STATUS_CLOSED = 'closed'
    STATUS_DRAFT = 'draft'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_DRAFT, 'Draft'),
    ]

    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='jobs',
        help_text="Recruiter owner of this job posting"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(help_text="Detailed description of the job role and responsibilities")
    required_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="List of mandatory required skills (e.g. ['Python', 'Django', 'PostgreSQL'])"
    )
    preferred_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="List of preferred nice-to-have skills (e.g. ['Docker', 'AWS', 'Redis'])"
    )
    min_experience = models.FloatField(
        default=0.0,
        help_text="Minimum years of professional experience required"
    )
    max_experience = models.FloatField(
        null=True,
        blank=True,
        help_text="Maximum years of professional experience (optional)"
    )
    # minimum_score is OPTIONAL / nullable
    minimum_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Optional threshold qualification score (0-100)"
    )
    # shortlist_count is OPTIONAL / nullable
    shortlist_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional maximum number of candidates to shortlist"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        help_text="Job posting status"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Job'
        verbose_name_plural = 'Jobs'

    def __str__(self):
        return f"{self.title} ({self.get_status_display()}) - Recruiter: {self.recruiter.email}"

    @property
    def experience_range_display(self):
        if self.max_experience:
            return f"{self.min_experience:g} - {self.max_experience:g} years"
        return f"{self.min_experience:g}+ years"

    @property
    def review_count(self):
        return self.screenings.filter(status='review').count()

    @property
    def shortlisted_count(self):
        return self.screenings.filter(status='shortlisted').count()

    @property
    def rejected_count(self):
        return self.screenings.filter(status='rejected').count()


class ScreeningResult(models.Model):
    """
    Stores the evaluation of a candidate against a job description.
    
    The breakdown of semantic matches is populated via LLM extraction,
    while all numerical scores and the final total score (0-100) are
    computed strictly by a deterministic Python scoring engine.
    """
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='screenings'
    )
    resume = models.ForeignKey(
        'resumes.Resume',
        on_delete=models.CASCADE,
        related_name='screenings',
        null=True,
        blank=True,
        help_text="Resume associated with this screening result"
    )
    # LLM Extracted Structured Information
    matched_required_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Required skills present in candidate resume"
    )
    missing_required_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Required skills absent from candidate resume"
    )
    matched_preferred_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Preferred skills present in candidate resume"
    )
    missing_preferred_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Preferred skills absent from candidate resume"
    )
    candidate_experience_years = models.FloatField(
        default=0.0,
        help_text="Extracted total years of experience"
    )
    candidate_education = models.CharField(
        max_length=255,
        blank=True,
        help_text="Extracted education credentials summary string"
    )
    candidate_education_json = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured education list [{'degree': ..., 'field': ...}]"
    )
    candidate_projects_summary = models.TextField(
        blank=True,
        help_text="Summary of relevant projects extracted from resume"
    )
    candidate_projects_json = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured projects list [{'name': ..., 'description': ...}]"
    )
    raw_ai_analysis = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw structured JSON response returned by LLM"
    )

    # Deterministic Engine Calculated Scores (NOT populated in Phase 4)
    # Required Skills (40%), Preferred Skills (15%), Experience (20%), Education (10%), Projects (15%)
    required_skills_score = models.FloatField(
        default=0.0,
        help_text="Deterministic score for required skills (0.0 to 40.0)"
    )
    preferred_skills_score = models.FloatField(
        default=0.0,
        help_text="Deterministic score for preferred skills (0.0 to 15.0)"
    )
    experience_score = models.FloatField(
        default=0.0,
        help_text="Deterministic score for experience match (0.0 to 20.0)"
    )
    education_score = models.FloatField(
        default=0.0,
        help_text="Deterministic score for education match (0.0 to 10.0)"
    )
    projects_score = models.FloatField(
        default=0.0,
        help_text="Deterministic score for projects match (0.0 to 15.0)"
    )
    total_score = models.FloatField(
        default=0.0,
        help_text="Final deterministic total score (0.0 to 100.0)"
    )

    # LLM Generated Executive Summary
    candidate_summary = models.TextField(
        blank=True,
        help_text="Short narrative summary generated by the LLM"
    )

    # Recruiter Decision & Notes (Phase 7)
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
        help_text="Recruiter decision status: review, shortlisted, rejected"
    )
    recruiter_notes = models.TextField(
        blank=True,
        default='',
        help_text="Recruiter evaluation notes and comments"
    )

    screened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-screened_at']
        verbose_name = 'Screening Result'
        verbose_name_plural = 'Screening Results'

    def set_decision(self, new_status):
        """Updates the decision across the screening result and linked Resume."""
        if new_status in (self.STATUS_REVIEW, self.STATUS_SHORTLISTED, self.STATUS_REJECTED):
            self.status = new_status
            self.save(update_fields=['status'])
            if self.resume and hasattr(self.resume, 'status'):
                self.resume.status = new_status
                self.resume.save(update_fields=['status'])
            return True
        return False

    def __str__(self):
        cand_name = self.candidate_name
        return f"{cand_name} -> {self.job.title} (Score: {self.total_score:.1f}/100)"

    @property
    def required_skill_score(self):
        return self.required_skills_score

    @property
    def preferred_skill_score(self):
        return self.preferred_skills_score

    @property
    def project_score(self):
        return self.projects_score

    @property
    def final_score(self):
        return self.total_score

    @property
    def candidate_name(self):
        if self.resume:
            return self.resume.candidate_name or self.resume.filename
        return "Unknown Candidate"

    @property
    def candidate_email(self):
        if self.resume and self.resume.candidate_email:
            return self.resume.candidate_email
        return ""

    @property
    def all_matched_skills(self):
        req = self.matched_required_skills or []
        pref = self.matched_preferred_skills or []
        # Return combined unique preserved order
        seen = set()
        combined = []
        for s in req + pref:
            if s and s.lower() not in seen:
                seen.add(s.lower())
                combined.append(s)
        return combined

    @property
    def all_missing_skills(self):
        req = self.missing_required_skills or []
        pref = self.missing_preferred_skills or []
        seen = set()
        combined = []
        for s in req + pref:
            if s and s.lower() not in seen:
                seen.add(s.lower())
                combined.append(s)
        return combined
