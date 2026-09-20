import json
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from .models import Job, ScreeningResult
from resumes.models import Resume

User = get_user_model()


class JobModelTests(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user(
            email='recruiter@company.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='One'
        )

    def test_job_creation_with_all_fields(self):
        job = Job.objects.create(
            recruiter=self.recruiter,
            title="Senior Backend Engineer",
            description="Looking for an experienced Django & Python engineer.",
            required_skills=["Python", "Django", "PostgreSQL"],
            preferred_skills=["Docker", "AWS", "Redis"],
            min_experience=3.0,
            max_experience=6.0,
            minimum_score=75.0,
            shortlist_count=5,
            status=Job.STATUS_ACTIVE
        )
        self.assertEqual(job.title, "Senior Backend Engineer")
        self.assertEqual(job.recruiter, self.recruiter)
        self.assertEqual(job.minimum_score, 75.0)
        self.assertEqual(job.shortlist_count, 5)
        self.assertEqual(job.experience_range_display, "3 - 6 years")

    def test_job_creation_without_minimum_score_and_shortlist_count(self):
        """
        Specification:
        minimum_score is OPTIONAL / nullable.
        shortlist_count is OPTIONAL / nullable.
        Recruiters must be allowed to create jobs without entering either value.
        """
        job = Job.objects.create(
            recruiter=self.recruiter,
            title="Frontend Developer",
            description="Vue/React/Vanilla JS developer.",
            required_skills=["HTML", "CSS", "JavaScript"],
            min_experience=1.5,
            minimum_score=None,
            shortlist_count=None
        )
        self.assertIsNone(job.minimum_score)
        self.assertIsNone(job.shortlist_count)
        self.assertEqual(job.experience_range_display, "1.5+ years")


class JobViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.recruiter_a = User.objects.create_user(
            email='recruiter_a@company.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='A'
        )
        self.recruiter_b = User.objects.create_user(
            email='recruiter_b@company.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='B'
        )

        self.job_a = Job.objects.create(
            recruiter=self.recruiter_a,
            title="Python Architect",
            description="Deep architecture experience required.",
            required_skills=["Python", "System Design"],
            min_experience=7.0
        )
        self.job_b = Job.objects.create(
            recruiter=self.recruiter_b,
            title="DevOps Specialist",
            description="Infrastructure and CI/CD.",
            required_skills=["Terraform", "Kubernetes"],
            min_experience=4.0
        )

    def test_job_list_shows_only_own_jobs(self):
        """Recruiter A sees Job A, but cannot see Job B."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        response = self.client.get(reverse('job_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Python Architect')
        self.assertNotContains(response, 'DevOps Specialist')

    def test_create_job_via_view_with_optional_thresholds_empty(self):
        """Recruiter creates a job without minimum_score or shortlist_count."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        response = self.client.post(reverse('job_create'), {
            'title': 'Junior Data Analyst',
            'status': 'active',
            'description': 'Analyze business metrics and reports.',
            'required_skills_input': 'SQL, Excel, Python',
            'preferred_skills_input': 'Tableau, PowerBI',
            'min_experience': '1.0',
            'max_experience': '',
            'minimum_score': '',
            'shortlist_count': '',
        })
        new_job = Job.objects.get(title='Junior Data Analyst')
        self.assertEqual(new_job.recruiter, self.recruiter_a)
        self.assertIsNone(new_job.minimum_score)
        self.assertIsNone(new_job.shortlist_count)
        self.assertEqual(new_job.required_skills, ['SQL', 'Excel', 'Python'])
        self.assertEqual(new_job.preferred_skills, ['Tableau', 'PowerBI'])
        self.assertRedirects(response, reverse('job_detail', kwargs={'pk': new_job.pk}))

    def test_view_own_job_detail(self):
        """Recruiter A can view their own job detail with all sections."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        response = self.client.get(reverse('job_detail', kwargs={'pk': self.job_a.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Python Architect')
        self.assertContains(response, 'Role Specifications')
        self.assertContains(response, 'System Design')

    def test_edit_own_job(self):
        """Recruiter A can edit their own job."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        response = self.client.post(reverse('job_edit', kwargs={'pk': self.job_a.pk}), {
            'title': 'Lead Python Architect',
            'status': 'active',
            'description': 'Updated description.',
            'required_skills_input': 'Python, System Design, FastAPI',
            'preferred_skills_input': 'Kafka',
            'min_experience': '8.0',
            'max_experience': '12.0',
            'minimum_score': '80',
            'shortlist_count': '3',
        })
        self.job_a.refresh_from_db()
        self.assertEqual(self.job_a.title, 'Lead Python Architect')
        self.assertEqual(self.job_a.minimum_score, 80.0)
        self.assertEqual(self.job_a.shortlist_count, 3)
        self.assertIn('FastAPI', self.job_a.required_skills)
        self.assertRedirects(response, reverse('job_detail', kwargs={'pk': self.job_a.pk}))

    def test_delete_own_job(self):
        """Recruiter A can delete their own job."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        job_id = self.job_a.pk
        response = self.client.post(reverse('job_delete', kwargs={'pk': job_id}))
        self.assertRedirects(response, reverse('job_list'))
        self.assertFalse(Job.objects.filter(pk=job_id).exists())

    def test_recruiter_cannot_access_another_recruiters_job(self):
        """
        Specification:
        Recruiters MUST NOT access another recruiter's jobs.
        """
        # Recruiter B attempts to access Job A
        self.client.login(email='recruiter_b@company.com', password='Password123!')

        # 1. Detail view must return 404
        detail_response = self.client.get(reverse('job_detail', kwargs={'pk': self.job_a.pk}))
        self.assertEqual(detail_response.status_code, 404)

        # 2. Edit view must return 404
        edit_response = self.client.get(reverse('job_edit', kwargs={'pk': self.job_a.pk}))
        self.assertEqual(edit_response.status_code, 404)

        # 3. Delete POST must return 404 and NOT delete Job A
        delete_response = self.client.post(reverse('job_delete', kwargs={'pk': self.job_a.pk}))
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(Job.objects.filter(pk=self.job_a.pk).exists())


class DeterministicScoringTests(TestCase):
    """
    Tests for Phase 5: Deterministic candidate scoring engine.
    Verifies:
      - Default weights: 40% Required, 15% Preferred, 20% Experience, 10% Education, 15% Projects = 100%
      - Exact example from spec: 35/40 + 12/15 + 18/20 + 10/10 + 13/15 = 88/100
      - Determinism and reproducibility
      - Score bounds: guaranteed between 0.0 and 100.0
      - Candidate status strictly 'review'
      - Persistence via apply_scoring_to_screening_result
    """

    def setUp(self):
        self.recruiter = User.objects.create_user(
            email='recruiter@example.com',
            password='Password123!'
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title="Senior Python Engineer",
            description="Looking for Python and Django expertise.",
            required_skills=["Python", "Django", "PostgreSQL", "Git", "REST", "Linux", "SQL", "Docker"],
            preferred_skills=["AWS", "Redis", "CI/CD", "FastAPI", "Kubernetes"],
            min_experience=5.0
        )
        from resumes.models import Resume
        dummy_file = SimpleUploadedFile("candidate_resume.pdf", b"%PDF-1.4 dummy", content_type="application/pdf")
        self.resume = Resume.objects.create(
            recruiter=self.recruiter,
            job=self.job,
            file=dummy_file,
            extracted_text="Candidate resume text",
            status='review'
        )

    def test_exact_specification_breakdown_example(self):
        """
        Verifies the exact example from specification:
        Required Skills = 35/40
        Preferred Skills = 12/15
        Experience = 18/20
        Education = 10/10
        Projects = 13/15
        Final = 88/100
        """
        from screening.services.scoring import DeterministicScoringEngine
        engine = DeterministicScoringEngine()

        candidate_data = {
            'required_skill_score': 35.0,
            'preferred_skill_score': 12.0,
            'experience_score': 18.0,
            'education_score': 10.0,
            'project_score': 13.0,
        }

        result = engine.calculate_score(candidate_data, self.job)

        self.assertEqual(result['required_skill_score'], 35.0)
        self.assertEqual(result['preferred_skill_score'], 12.0)
        self.assertEqual(result['experience_score'], 18.0)
        self.assertEqual(result['education_score'], 10.0)
        self.assertEqual(result['project_score'], 13.0)
        self.assertEqual(result['final_score'], 88.0)
        self.assertEqual(result['status'], 'review')

    def test_structured_data_produces_exact_example_values(self):
        """
        Verifies that structured data matching the mathematical fractions produces 88/100:
          - Required: 7 of 8 skills matched -> 7/8 * 40 = 35.0
          - Preferred: 4 of 5 skills matched -> 4/5 * 15 = 12.0
          - Experience: 4.5 of 5.0 years -> 4.5/5.0 * 20 = 18.0
          - Education: B.Tech Computer Science -> 10.0
          - Projects: 2 projects (brief) -> 13.0
          - Final = 35.0 + 12.0 + 18.0 + 10.0 + 13.0 = 88.0
        """
        from screening.services.scoring import DeterministicScoringEngine
        engine = DeterministicScoringEngine()

        candidate_data = {
            'matched_required_skills': ["Python", "Django", "PostgreSQL", "Git", "REST", "Linux", "SQL"],
            'missing_required_skills': ["Docker"],
            'matched_preferred_skills': ["AWS", "Redis", "CI/CD", "FastAPI"],
            'missing_preferred_skills': ["Kubernetes"],
            'experience_years': 4.5,
            'education': [{'degree': 'B.Tech', 'field': 'Computer Science'}],
            'projects': [
                {'name': 'Project 1', 'description': 'Short summary'},
                {'name': 'Project 2', 'description': 'Short summary'}
            ]
        }

        result = engine.calculate_score(candidate_data, self.job)

        self.assertEqual(result['required_skill_score'], 35.0)
        self.assertEqual(result['preferred_skill_score'], 12.0)
        self.assertEqual(result['experience_score'], 18.0)
        self.assertEqual(result['education_score'], 10.0)
        self.assertEqual(result['project_score'], 13.0)
        self.assertEqual(result['final_score'], 88.0)
        self.assertEqual(result['status'], 'review')

    def test_perfect_score_calculation(self):
        """A candidate meeting all requirements achieves 100.0."""
        from screening.services.scoring import DeterministicScoringEngine
        engine = DeterministicScoringEngine()

        candidate_data = {
            'matched_required_skills': self.job.required_skills,
            'missing_required_skills': [],
            'matched_preferred_skills': self.job.preferred_skills,
            'missing_preferred_skills': [],
            'experience_years': 7.0,  # Exceeds 5.0
            'education': [{'degree': 'M.S.', 'field': 'Computer Science'}],
            'projects': [
                {'name': 'Distributed Cache', 'description': 'High performance caching layer with Redis clustering and Raft consensus.'},
                {'name': 'Microservices Mesh', 'description': 'Enterprise service mesh managing 500k RPS with zero latency degradation.'}
            ]
        }

        result = engine.calculate_score(candidate_data, self.job)

        self.assertEqual(result['required_skill_score'], 40.0)
        self.assertEqual(result['preferred_skill_score'], 15.0)
        self.assertEqual(result['experience_score'], 20.0)
        self.assertEqual(result['education_score'], 10.0)
        self.assertEqual(result['project_score'], 15.0)
        self.assertEqual(result['final_score'], 100.0)
        self.assertEqual(result['status'], 'review')

    def test_zero_score_calculation(self):
        """A candidate with no matches and empty background receives 0.0."""
        from screening.services.scoring import DeterministicScoringEngine
        engine = DeterministicScoringEngine()

        candidate_data = {
            'matched_required_skills': [],
            'missing_required_skills': self.job.required_skills,
            'matched_preferred_skills': [],
            'missing_preferred_skills': self.job.preferred_skills,
            'experience_years': 0.0,
            'education': [],
            'projects': []
        }

        result = engine.calculate_score(candidate_data, self.job)

        self.assertEqual(result['required_skill_score'], 0.0)
        self.assertEqual(result['preferred_skill_score'], 0.0)
        self.assertEqual(result['experience_score'], 0.0)
        self.assertEqual(result['education_score'], 0.0)
        self.assertEqual(result['project_score'], 0.0)
        self.assertEqual(result['final_score'], 0.0)
        self.assertEqual(result['status'], 'review')

    def test_score_guaranteed_bounded_between_0_and_100(self):
        """Engine strictly clamps scores within [0.0, 100.0]."""
        from screening.services.scoring import DeterministicScoringEngine
        engine = DeterministicScoringEngine()

        candidate_overflow = {
            'required_skill_score': 999.0,
            'preferred_skill_score': 999.0,
            'experience_score': 999.0,
            'education_score': 999.0,
            'project_score': 999.0,
        }
        result = engine.calculate_score(candidate_overflow, self.job)
        self.assertEqual(result['final_score'], 100.0)

        candidate_underflow = {
            'required_skill_score': -50.0,
            'preferred_skill_score': -50.0,
            'experience_score': -50.0,
            'education_score': -50.0,
            'project_score': -50.0,
        }
        result = engine.calculate_score(candidate_underflow, self.job)
        self.assertEqual(result['final_score'], 0.0)

    def test_candidate_status_strictly_review(self):
        """
        Specification:
        Candidate status MUST be: review.
        The scoring engine must never auto-shortlist or auto-reject candidates.
        """
        from screening.services.scoring import DeterministicScoringEngine
        engine = DeterministicScoringEngine()

        high_score_data = {
            'required_skill_score': 40.0,
            'preferred_skill_score': 15.0,
            'experience_score': 20.0,
            'education_score': 10.0,
            'project_score': 15.0,
        }
        result_high = engine.calculate_score(high_score_data, self.job)
        self.assertEqual(result_high['status'], 'review')

        low_score_data = {
            'required_skill_score': 0.0,
            'preferred_skill_score': 0.0,
            'experience_score': 0.0,
            'education_score': 0.0,
            'project_score': 0.0,
        }
        result_low = engine.calculate_score(low_score_data, self.job)
        self.assertEqual(result_low['status'], 'review')

    def test_apply_scoring_to_screening_result_persists_in_database(self):
        """
        Verifies apply_scoring_to_screening_result persists scores to ScreeningResult
        and leaves candidate/resume in review status.
        """
        from screening.services.scoring import apply_scoring_to_screening_result
        from resumes.models import Resume

        screening_result = ScreeningResult.objects.create(
            job=self.job,
            resume=self.resume,
            matched_required_skills=["Python", "Django"],
            missing_required_skills=["PostgreSQL", "Git", "REST", "Linux", "SQL", "Docker"],
            matched_preferred_skills=["AWS"],
            missing_preferred_skills=["Redis", "CI/CD", "FastAPI", "Kubernetes"],
            candidate_experience_years=5.0,
            candidate_education="B.Tech Computer Science",
            candidate_education_json=[{'degree': 'B.Tech', 'field': 'Computer Science'}],
            candidate_projects_json=[{'name': 'Web App', 'description': 'Full stack application'}],
            candidate_summary="Backend applicant",
            raw_ai_analysis={}
        )

        score_data = apply_scoring_to_screening_result(screening_result)
        screening_result.refresh_from_db()
        self.resume.refresh_from_db()

        # Database fields
        self.assertGreater(screening_result.total_score, 0.0)
        self.assertEqual(screening_result.experience_score, 20.0)
        self.assertEqual(screening_result.education_score, 10.0)

        # Property aliases
        self.assertEqual(screening_result.final_score, screening_result.total_score)
        self.assertEqual(screening_result.required_skill_score, screening_result.required_skills_score)
        self.assertEqual(screening_result.preferred_skill_score, screening_result.preferred_skills_score)
        self.assertEqual(screening_result.project_score, screening_result.projects_score)
        self.assertEqual(screening_result.status, 'review')
        self.assertEqual(self.resume.status, 'review')

    def test_custom_weights_must_sum_to_100(self):
        """Engine validates that category weights sum exactly to 100.0."""
        from screening.services.scoring import DeterministicScoringEngine
        with self.assertRaises(ValueError):
            DeterministicScoringEngine(weight_required_skills=50.0, weight_preferred_skills=50.0, weight_experience=20.0)


class ScreeningResultsViewTests(TestCase):
    """
    Tests for Phase 6: Screening Results, ranking, search, filtering, and Top-N.
    URL: /jobs/<job_id>/candidates/
    """
    def setUp(self):
        self.client = Client()
        self.recruiter_a = User.objects.create_user(
            email='recruiter_a@company.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='A'
        )
        self.recruiter_b = User.objects.create_user(
            email='recruiter_b@company.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='B'
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter_a,
            title="Senior Python Backend Developer",
            description="High scalability Python backend systems.",
            required_skills=["Python", "Django", "PostgreSQL"],
            preferred_skills=["Docker", "AWS", "Redis"],
            min_experience=3.0
        )

        # Candidate 1: High Score (92.0), 5 yrs exp
        self.resume_1 = Resume.objects.create(
            recruiter=self.recruiter_a,
            job=self.job,
            file=SimpleUploadedFile("alice.pdf", b"%PDF-1.4 dummy", content_type="application/pdf"),
            candidate_name="Alice Wonderland",
            candidate_email="alice@company.com",
            extracted_text="Alice resume Python Django Docker",
            status='review'
        )
        self.screening_1 = ScreeningResult.objects.create(
            job=self.job,
            resume=self.resume_1,
            total_score=92.0,
            required_skills_score=40.0,
            preferred_skills_score=12.0,
            experience_score=20.0,
            education_score=10.0,
            projects_score=10.0,
            candidate_experience_years=5.0,
            matched_required_skills=["Python", "Django"],
            missing_required_skills=["PostgreSQL"],
            matched_preferred_skills=["Docker"],
            missing_preferred_skills=["AWS", "Redis"],
        )

        # Candidate 2: Moderate Score (75.0), 4 yrs exp
        self.resume_2 = Resume.objects.create(
            recruiter=self.recruiter_a,
            job=self.job,
            file=SimpleUploadedFile("bob.pdf", b"%PDF-1.4 dummy", content_type="application/pdf"),
            candidate_name="Bob Builder",
            candidate_email="bob@builder.com",
            extracted_text="Bob resume Python Redis",
            status='review'
        )
        self.screening_2 = ScreeningResult.objects.create(
            job=self.job,
            resume=self.resume_2,
            total_score=75.0,
            required_skills_score=30.0,
            preferred_skills_score=10.0,
            experience_score=15.0,
            education_score=10.0,
            projects_score=10.0,
            candidate_experience_years=4.0,
            matched_required_skills=["Python"],
            missing_required_skills=["Django", "PostgreSQL"],
            matched_preferred_skills=["Redis"],
            missing_preferred_skills=["Docker", "AWS"],
        )

        # Candidate 3: Tied Score with Candidate 2 (75.0), but lower experience (2 yrs)
        self.resume_3 = Resume.objects.create(
            recruiter=self.recruiter_a,
            job=self.job,
            file=SimpleUploadedFile("charlie.pdf", b"%PDF-1.4 dummy", content_type="application/pdf"),
            candidate_name="Charlie Chaplin",
            candidate_email="charlie@cinema.com",
            extracted_text="Charlie resume Django AWS",
            status='review'
        )
        self.screening_3 = ScreeningResult.objects.create(
            job=self.job,
            resume=self.resume_3,
            total_score=75.0,
            required_skills_score=30.0,
            preferred_skills_score=10.0,
            experience_score=10.0,
            education_score=10.0,
            projects_score=15.0,
            candidate_experience_years=2.0,
            matched_required_skills=["Django"],
            missing_required_skills=["Python", "PostgreSQL"],
            matched_preferred_skills=["AWS"],
            missing_preferred_skills=["Docker", "Redis"],
        )

        # Candidate 4: Lower Score (50.0), 1 yr exp
        self.resume_4 = Resume.objects.create(
            recruiter=self.recruiter_a,
            job=self.job,
            file=SimpleUploadedFile("david.pdf", b"%PDF-1.4 dummy", content_type="application/pdf"),
            candidate_name="David Copperfield",
            candidate_email="david@magic.com",
            extracted_text="David resume",
            status='review'
        )
        self.screening_4 = ScreeningResult.objects.create(
            job=self.job,
            resume=self.resume_4,
            total_score=50.0,
            required_skills_score=20.0,
            preferred_skills_score=5.0,
            experience_score=5.0,
            education_score=10.0,
            projects_score=10.0,
            candidate_experience_years=1.0,
            matched_required_skills=[],
            missing_required_skills=["Python", "Django", "PostgreSQL"],
            matched_preferred_skills=[],
            missing_preferred_skills=["Docker", "AWS", "Redis"],
        )

    def test_access_control_recruiter_ownership(self):
        """Recruiter A can access own candidates; Recruiter B receives 404; unauthenticated redirected."""
        url = reverse('job_candidates', kwargs={'job_id': self.job.id})

        # 1. Recruiter A (owner) gets 200 OK
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Senior Python Backend Developer')
        self.assertContains(response, 'Alice Wonderland')

        # 2. Recruiter B (not owner) gets 404 Not Found
        self.client.login(email='recruiter_b@company.com', password='Password123!')
        response_b = self.client.get(url)
        self.assertEqual(response_b.status_code, 404)

        # 3. Anonymous user redirected to login
        self.client.logout()
        response_anon = self.client.get(url)
        self.assertEqual(response_anon.status_code, 302)

    def test_default_ranking_final_score_desc_and_stable_tie_breaking(self):
        """
        Candidates must be ranked by final_score DESC with stable secondary tie-breaker.
        Alice (92.0) -> Rank 1
        Bob (75.0, 4.0 exp) -> Rank 2 (tie broken by higher experience score)
        Charlie (75.0, 2.0 exp) -> Rank 3
        David (50.0) -> Rank 4
        """
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        url = reverse('job_candidates', kwargs={'job_id': self.job.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        candidates = list(response.context['candidates'])

        self.assertEqual(len(candidates), 4)
        self.assertEqual(candidates[0].candidate_name, "Alice Wonderland")
        self.assertEqual(candidates[0].calculated_rank, 1)

        self.assertEqual(candidates[1].candidate_name, "Bob Builder")
        self.assertEqual(candidates[1].calculated_rank, 2)

        self.assertEqual(candidates[2].candidate_name, "Charlie Chaplin")
        self.assertEqual(candidates[2].calculated_rank, 3)

        self.assertEqual(candidates[3].candidate_name, "David Copperfield")
        self.assertEqual(candidates[3].calculated_rank, 4)

    def test_search_by_name_email_and_skill(self):
        """Search query matches candidate name, email, or skill."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        url = reverse('job_candidates', kwargs={'job_id': self.job.id})

        # Name search
        res_name = self.client.get(url, {'q': 'Alice'})
        self.assertEqual(len(res_name.context['candidates']), 1)
        self.assertEqual(res_name.context['candidates'][0].candidate_name, "Alice Wonderland")

        # Email search
        res_email = self.client.get(url, {'q': 'bob@builder.com'})
        self.assertEqual(len(res_email.context['candidates']), 1)
        self.assertEqual(res_email.context['candidates'][0].candidate_name, "Bob Builder")

        # Skill search (Docker is present in Alice's skills)
        res_skill = self.client.get(url, {'q': 'Docker'})
        cand_names = [c.candidate_name for c in res_skill.context['candidates']]
        self.assertIn("Alice Wonderland", cand_names)

    def test_filter_by_score_and_experience(self):
        """Filters candidates by min_score, max_score, and experience."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        url = reverse('job_candidates', kwargs={'job_id': self.job.id})

        # Min score >= 80
        res_min = self.client.get(url, {'min_score': '80'})
        self.assertEqual(len(res_min.context['candidates']), 1)
        self.assertEqual(res_min.context['candidates'][0].candidate_name, "Alice Wonderland")

        # Max score <= 60
        res_max = self.client.get(url, {'max_score': '60'})
        self.assertEqual(len(res_max.context['candidates']), 1)
        self.assertEqual(res_max.context['candidates'][0].candidate_name, "David Copperfield")

        # Experience >= 4.0
        res_exp = self.client.get(url, {'experience': '4.0'})
        names = [c.candidate_name for c in res_exp.context['candidates']]
        self.assertIn("Alice Wonderland", names)
        self.assertIn("Bob Builder", names)
        self.assertNotIn("Charlie Chaplin", names)
        self.assertNotIn("David Copperfield", names)

    def test_sorting_options(self):
        """Verifies sorting by score ascending, experience, and name."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        url = reverse('job_candidates', kwargs={'job_id': self.job.id})

        # Lowest score first (score_asc)
        res_asc = self.client.get(url, {'sort': 'score_asc'})
        self.assertEqual(res_asc.context['candidates'][0].candidate_name, "David Copperfield")

        # Name alphabetical (name_asc)
        res_name = self.client.get(url, {'sort': 'name_asc'})
        self.assertEqual(res_name.context['candidates'][0].candidate_name, "Alice Wonderland")
        self.assertEqual(res_name.context['candidates'][1].candidate_name, "Bob Builder")
        self.assertEqual(res_name.context['candidates'][2].candidate_name, "Charlie Chaplin")
        self.assertEqual(res_name.context['candidates'][3].candidate_name, "David Copperfield")

    def test_top_n_filtering_does_not_mutate_candidate_status(self):
        """
        Specification:
        Top-N must ONLY filter/recommend candidates.
        It must NOT change status.
        Filtering must NEVER change candidate status.
        All candidates should remain Review until recruiter manually changes the status.
        """
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        url = reverse('job_candidates', kwargs={'job_id': self.job.id})

        # Request Top 2 candidates
        response = self.client.get(url, {'top_n': '2'})
        self.assertEqual(len(response.context['candidates']), 2)
        top_names = [c.candidate_name for c in response.context['candidates']]
        self.assertEqual(top_names, ["Alice Wonderland", "Bob Builder"])

        # Crucial: Verify all candidates in database remain 'review'
        self.resume_1.refresh_from_db()
        self.resume_2.refresh_from_db()
        self.resume_3.refresh_from_db()
        self.resume_4.refresh_from_db()

        self.assertEqual(self.resume_1.status, 'review')
        self.assertEqual(self.resume_2.status, 'review')
        self.assertEqual(self.resume_3.status, 'review')
        self.assertEqual(self.resume_4.status, 'review')

    def test_table_columns_and_badges_rendered(self):
        """Verifies table columns, chips, and badges are rendered in HTML."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        url = reverse('job_candidates', kwargs={'job_id': self.job.id})
        response = self.client.get(url)

        self.assertContains(response, 'Rank')
        self.assertContains(response, 'Candidate')
        self.assertContains(response, 'Score')
        self.assertContains(response, 'Experience')
        self.assertContains(response, 'Matched Skills')
        self.assertContains(response, 'Missing Skills')
        self.assertContains(response, 'Status')
        self.assertContains(response, 'Action')
        self.assertContains(response, 'Review')
        self.assertContains(response, 'View Details')
        self.assertContains(response, 'Top 5')
        self.assertContains(response, 'Top 10')
        self.assertContains(response, 'Top 20')


class RecruiterDecisionWorkflowTests(TestCase):
    """
    Tests for Phase 7: Recruiter decision workflow, status lifecycle,
    recruiter notes, and bulk actions.
    """
    def setUp(self):
        self.client = Client()
        self.recruiter_a = User.objects.create_user(
            email='recruiter_a@company.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='A'
        )
        self.recruiter_b = User.objects.create_user(
            email='recruiter_b@company.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='B'
        )
        self.job_a = Job.objects.create(
            recruiter=self.recruiter_a,
            title="Senior Django Developer",
            description="Django backend systems",
            required_skills=["Python", "Django"],
            preferred_skills=["PostgreSQL"],
            min_experience=3.0
        )
        self.job_b = Job.objects.create(
            recruiter=self.recruiter_b,
            title="Frontend Specialist",
            description="React / UI",
            required_skills=["HTML", "CSS"],
            min_experience=2.0
        )

        # 5 Candidates for Job A with varying scores
        self.candidates_a = []
        for i, score in enumerate([95.0, 90.0, 85.0, 80.0, 70.0]):
            res = Resume.objects.create(
                recruiter=self.recruiter_a,
                job=self.job_a,
                file=SimpleUploadedFile(f"cand_{i}.pdf", b"%PDF-1.4 dummy", content_type="application/pdf"),
                candidate_name=f"Applicant {i+1}",
                candidate_email=f"app{i+1}@test.com",
                extracted_text="Resume content",
                status='review'
            )
            sc = ScreeningResult.objects.create(
                job=self.job_a,
                resume=res,
                total_score=score,
                required_skills_score=35.0,
                preferred_skills_score=15.0,
                experience_score=15.0,
                education_score=10.0,
                projects_score=max(0.0, score - 75.0),
                candidate_experience_years=float(i + 1),
                status='review',
                candidate_summary=f"Summary for Applicant {i+1}"
            )
            self.candidates_a.append(sc)

    def test_candidate_detail_page_renders_all_elements(self):
        """Verifies candidate detail page shows scores, breakdown, notes, and decisions."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        cand = self.candidates_a[0]
        url = reverse('candidate_detail', kwargs={'job_id': self.job_a.id, 'candidate_id': cand.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Applicant 1')
        self.assertContains(response, '95.0')
        self.assertContains(response, 'Required Skills (40%)')
        self.assertContains(response, 'Preferred Skills (15%)')
        self.assertContains(response, 'Experience (20%)')
        self.assertContains(response, 'Education (10%)')
        self.assertContains(response, 'Projects (15%)')
        self.assertContains(response, 'Shortlist')
        self.assertContains(response, 'Keep in Review')
        self.assertContains(response, 'Reject')
        self.assertContains(response, 'Save Notes')

    def test_status_transitions_and_bidirectionality(self):
        """
        Verifies:
        - Starts as review
        - review -> shortlisted
        - shortlisted -> review
        - review -> rejected
        - rejected -> review
        """
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        cand = self.candidates_a[0]
        url = reverse('candidate_detail', kwargs={'job_id': self.job_a.id, 'candidate_id': cand.id})

        # Starts in review
        self.assertEqual(cand.status, 'review')

        # 1. Shortlist
        self.client.post(url, {'action': 'shortlist'})
        cand.refresh_from_db()
        self.assertEqual(cand.status, 'shortlisted')
        self.assertEqual(cand.resume.status, 'shortlisted')

        # 2. Shortlisted -> Review
        self.client.post(url, {'action': 'review'})
        cand.refresh_from_db()
        self.assertEqual(cand.status, 'review')
        self.assertEqual(cand.resume.status, 'review')

        # 3. Review -> Rejected
        self.client.post(url, {'action': 'reject'})
        cand.refresh_from_db()
        self.assertEqual(cand.status, 'rejected')
        self.assertEqual(cand.resume.status, 'rejected')

        # 4. Rejected -> Review
        self.client.post(url, {'action': 'review'})
        cand.refresh_from_db()
        self.assertEqual(cand.status, 'review')
        self.assertEqual(cand.resume.status, 'review')

    def test_candidate_status_api_patch(self):
        """Verifies candidate status API handles PATCH requests."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        cand = self.candidates_a[0]
        url = reverse('candidate_status_api', kwargs={'job_id': self.job_a.id, 'candidate_id': cand.id})

        response = self.client.patch(
            url,
            data=json.dumps({'status': 'shortlisted'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        cand.refresh_from_db()
        self.assertEqual(cand.status, 'shortlisted')

    def test_recruiter_notes_persistence(self):
        """Verifies recruiter notes saving via view POST and API PATCH."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        cand = self.candidates_a[1]

        # 1. Via Form POST
        detail_url = reverse('candidate_detail', kwargs={'job_id': self.job_a.id, 'candidate_id': cand.id})
        self.client.post(detail_url, {'action': 'save_notes', 'recruiter_notes': 'Great communication skills'})
        cand.refresh_from_db()
        self.assertEqual(cand.recruiter_notes, 'Great communication skills')
        self.assertEqual(cand.resume.recruiter_notes, 'Great communication skills')

        # 2. Via PATCH API
        api_url = reverse('candidate_notes_api', kwargs={'job_id': self.job_a.id, 'candidate_id': cand.id})
        response = self.client.patch(
            api_url,
            data=json.dumps({'notes': 'Updated: Scheduled for tech round'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        cand.refresh_from_db()
        self.assertEqual(cand.recruiter_notes, 'Updated: Scheduled for tech round')

    def test_bulk_shortlist(self):
        """Verifies bulk shortlist updates selected candidates only."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        url = reverse('bulk_shortlist', kwargs={'job_id': self.job_a.id})
        selected_ids = [self.candidates_a[0].id, self.candidates_a[1].id]

        response = self.client.post(
            url,
            data=json.dumps({'candidate_ids': selected_ids}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        for c in self.candidates_a:
            c.refresh_from_db()

        self.assertEqual(self.candidates_a[0].status, 'shortlisted')
        self.assertEqual(self.candidates_a[1].status, 'shortlisted')
        self.assertEqual(self.candidates_a[2].status, 'review')
        self.assertEqual(self.candidates_a[3].status, 'review')
        self.assertEqual(self.candidates_a[4].status, 'review')

    def test_bulk_reject(self):
        """Verifies bulk reject updates selected candidates only."""
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        url = reverse('bulk_reject', kwargs={'job_id': self.job_a.id})
        selected_ids = [self.candidates_a[3].id, self.candidates_a[4].id]

        response = self.client.post(
            url,
            data=json.dumps({'candidate_ids': selected_ids}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        for c in self.candidates_a:
            c.refresh_from_db()

        self.assertEqual(self.candidates_a[0].status, 'review')
        self.assertEqual(self.candidates_a[1].status, 'review')
        self.assertEqual(self.candidates_a[2].status, 'review')
        self.assertEqual(self.candidates_a[3].status, 'rejected')
        self.assertEqual(self.candidates_a[4].status, 'rejected')

    def test_bulk_shortlist_and_reject_unselected_within_filter_only(self):
        """
        Specification Example:
        100 candidates, Filter: Score >= 85 -> 24 candidates visible, Recruiter selects 15.
        Shortlist Selected & Reject Unselected:
        15 -> Shortlisted
        9 -> Rejected
        Candidates outside current filtered result set MUST remain unchanged.

        Tested on our 5 candidates:
        Candidates: [C1(95), C2(90), C3(85), C4(80), C5(70)]
        Filter (score >= 85) -> Visible set: [C1, C2, C3]
        Recruiter selects [C1, C2] out of [C1, C2, C3].
        Result:
        - C1, C2 -> Shortlisted
        - C3 -> Rejected
        - C4, C5 -> MUST remain Review!
        """
        self.client.login(email='recruiter_a@company.com', password='Password123!')
        url = reverse('bulk_shortlist_reject_unselected', kwargs={'job_id': self.job_a.id})

        visible_ids = [self.candidates_a[0].id, self.candidates_a[1].id, self.candidates_a[2].id]
        selected_ids = [self.candidates_a[0].id, self.candidates_a[1].id]

        response = self.client.post(
            url,
            data=json.dumps({
                'selected_ids': selected_ids,
                'visible_ids': visible_ids
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        for c in self.candidates_a:
            c.refresh_from_db()

        # Selected within filter -> Shortlisted
        self.assertEqual(self.candidates_a[0].status, 'shortlisted')
        self.assertEqual(self.candidates_a[1].status, 'shortlisted')

        # Unselected within filter -> Rejected
        self.assertEqual(self.candidates_a[2].status, 'rejected')

        # OUTSIDE filter -> MUST remain Review!
        self.assertEqual(self.candidates_a[3].status, 'review')
        self.assertEqual(self.candidates_a[4].status, 'review')

    def test_cross_recruiter_security_enforcement(self):
        """
        Enforce recruiter ownership on every operation:
        Recruiter B cannot view or tamper with Recruiter A's candidates or jobs.
        """
        self.client.login(email='recruiter_b@company.com', password='Password123!')
        target_cand = self.candidates_a[0]

        # 1. Detail page -> 404
        detail_url = reverse('candidate_detail', kwargs={'job_id': self.job_a.id, 'candidate_id': target_cand.id})
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, 404)

        # 2. Status API -> 404
        status_url = reverse('candidate_status_api', kwargs={'job_id': self.job_a.id, 'candidate_id': target_cand.id})
        res_status = self.client.patch(
            status_url,
            data=json.dumps({'status': 'shortlisted'}),
            content_type='application/json'
        )
        self.assertEqual(res_status.status_code, 404)

        # 3. Notes API -> 404
        notes_url = reverse('candidate_notes_api', kwargs={'job_id': self.job_a.id, 'candidate_id': target_cand.id})
        res_notes = self.client.patch(
            notes_url,
            data=json.dumps({'notes': 'Hacked notes'}),
            content_type='application/json'
        )
        self.assertEqual(res_notes.status_code, 404)

        # 4. Bulk shortlist -> 404
        bulk_short_url = reverse('bulk_shortlist', kwargs={'job_id': self.job_a.id})
        res_bulk_short = self.client.post(
            bulk_short_url,
            data=json.dumps({'candidate_ids': [target_cand.id]}),
            content_type='application/json'
        )
        self.assertEqual(res_bulk_short.status_code, 404)

        # 5. Bulk reject -> 404
        bulk_rej_url = reverse('bulk_reject', kwargs={'job_id': self.job_a.id})
        res_bulk_rej = self.client.post(
            bulk_rej_url,
            data=json.dumps({'candidate_ids': [target_cand.id]}),
            content_type='application/json'
        )
        self.assertEqual(res_bulk_rej.status_code, 404)

        # 6. Bulk Shortlist & Reject Unselected -> 404
        bulk_sru_url = reverse('bulk_shortlist_reject_unselected', kwargs={'job_id': self.job_a.id})
        res_bulk_sru = self.client.post(
            bulk_sru_url,
            data=json.dumps({'selected_ids': [target_cand.id], 'visible_ids': [target_cand.id]}),
            content_type='application/json'
        )
        self.assertEqual(res_bulk_sru.status_code, 404)

        # Verify candidate in DB was NOT modified
        target_cand.refresh_from_db()
        self.assertEqual(target_cand.status, 'review')
        self.assertEqual(target_cand.recruiter_notes, '')


class LockedPageArchitectureAndAuditTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.recruiter_a = User.objects.create_user(
            email='recruiter_a@audit.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='A'
        )
        self.recruiter_b = User.objects.create_user(
            email='recruiter_b@audit.com',
            password='Password123!',
            first_name='Recruiter',
            last_name='B'
        )
        self.job_a = Job.objects.create(
            recruiter=self.recruiter_a,
            title='Backend Python Engineer',
            description='Django backend developer.',
            status=Job.STATUS_ACTIVE
        )
        self.resume_a = Resume.objects.create(
            recruiter=self.recruiter_a,
            job=self.job_a,
            candidate_name='Alice Smith',
            candidate_email='alice@audit.com'
        )
        self.screening_a = ScreeningResult.objects.create(
            job=self.job_a,
            resume=self.resume_a,
            total_score=92.0,
            status=ScreeningResult.STATUS_SHORTLISTED
        )

    def test_public_routes_login_and_register(self):
        """Verify /login/ and /register/ are accessible to unauthenticated users."""
        res_login = self.client.get('/login/')
        self.assertEqual(res_login.status_code, 200)

        res_register = self.client.get('/register/')
        self.assertEqual(res_register.status_code, 200)

    def test_dashboard_real_statistics_accuracy(self):
        """Verify dashboard accurately aggregates active jobs, resumes, review, and shortlisted candidates."""
        self.client.force_login(self.recruiter_a)
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_jobs_count'], 1)
        self.assertEqual(res.context['total_resumes'], 1)
        self.assertEqual(res.context['shortlisted_candidates'], 1)
        self.assertEqual(res.context['in_review_candidates'], 0)

    def test_shortlisted_page_and_move_to_review(self):
        """Verify /shortlisted/ shows shortlisted candidates and allows moving them to review."""
        self.client.force_login(self.recruiter_a)
        res = self.client.get(reverse('shortlisted_candidates'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Alice Smith')

        # Move to review
        res_post = self.client.post(
            reverse('shortlisted_candidates'),
            {'action': 'move_to_review', 'candidate_id': self.screening_a.id}
        )
        self.assertEqual(res_post.status_code, 302)
        self.screening_a.refresh_from_db()
        self.assertEqual(self.screening_a.status, 'review')

    def test_shortlisted_cross_recruiter_isolation(self):
        """Recruiter B cannot see or move Recruiter A's shortlisted candidate."""
        self.client.force_login(self.recruiter_b)
        res = self.client.get(reverse('shortlisted_candidates'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'Alice Smith')

        # Recruiter B tries to move Recruiter A's candidate
        res_post = self.client.post(
            reverse('shortlisted_candidates'),
            {'action': 'move_to_review', 'candidate_id': self.screening_a.id}
        )
        self.assertEqual(res_post.status_code, 404)

    def test_direct_candidate_url_and_isolation(self):
        """Verify /candidates/<candidate_id>/ redirects to candidate detail and enforces ownership."""
        self.client.force_login(self.recruiter_a)
        res = self.client.get(reverse('candidate_detail_direct', kwargs={'candidate_id': self.screening_a.id}))
        self.assertEqual(res.status_code, 302)
        self.assertIn(f'/jobs/{self.job_a.id}/candidates/{self.screening_a.id}/', res.url)

        # Recruiter B gets 404
        self.client.force_login(self.recruiter_b)
        res_b = self.client.get(reverse('candidate_detail_direct', kwargs={'candidate_id': self.screening_a.id}))
        self.assertEqual(res_b.status_code, 404)

    def test_candidates_hub_navigation(self):
        """Verify /candidates/ redirects to active job's candidates page."""
        self.client.force_login(self.recruiter_a)
        res = self.client.get(reverse('candidates_hub'))
        self.assertEqual(res.status_code, 302)
        self.assertIn(f'/jobs/{self.job_a.id}/candidates/', res.url)

    def test_job_upload_url_and_isolation(self):
        """Verify /jobs/<job_id>/upload/ renders upload view and enforces ownership."""
        self.client.force_login(self.recruiter_a)
        res = self.client.get(reverse('job_resume_upload', kwargs={'job_id': self.job_a.id}))
        self.assertEqual(res.status_code, 200)

        # Recruiter B gets 404
        self.client.force_login(self.recruiter_b)
        res_b = self.client.get(reverse('job_resume_upload', kwargs={'job_id': self.job_a.id}))
        self.assertEqual(res_b.status_code, 404)


class AsyncJSONApiTests(TestCase):
    """Verifies the asynchronous JSON endpoints consumed by the JavaScript frontend."""

    def setUp(self):
        self.recruiter = User.objects.create_user(
            email='recruiter_api@test.com',
            password='Password123!',
            first_name='Recruiter',
            role='recruiter'
        )
        self.superuser = User.objects.create_superuser(
            email='super_api@test.com',
            password='AdminPassword123!',
            first_name='Admin'
        )
        self.other_recruiter = User.objects.create_user(
            email='other_api@test.com',
            password='Password123!',
            first_name='Other',
            role='recruiter'
        )

        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title='Fullstack JS Engineer',
            description='Django + Vanilla JS role',
            required_skills=['Python', 'JavaScript']
        )

        self.resume1 = Resume.objects.create(
            recruiter=self.recruiter,
            job=self.job,
            candidate_name='Candidate One',
            candidate_email='c1@test.com',
            file='resumes/test1.pdf',
            status='review'
        )
        self.screening1 = ScreeningResult.objects.create(
            job=self.job,
            resume=self.resume1,
            total_score=85.0,
            status='review'
        )

        self.resume2 = Resume.objects.create(
            recruiter=self.recruiter,
            job=self.job,
            candidate_name='Candidate Two',
            candidate_email='c2@test.com',
            file='resumes/test2.pdf',
            status='review'
        )
        self.screening2 = ScreeningResult.objects.create(
            job=self.job,
            resume=self.resume2,
            total_score=60.0,
            status='review'
        )

    def test_candidate_status_api_shortlist(self):
        self.client.force_login(self.recruiter)
        url = reverse('candidate_status_api', kwargs={'job_id': self.job.id, 'candidate_id': self.screening1.id})
        response = self.client.post(
            url,
            data=json.dumps({'status': 'shortlisted'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'shortlisted')

        self.screening1.refresh_from_db()
        self.assertEqual(self.screening1.status, 'shortlisted')

    def test_candidate_notes_api(self):
        self.client.force_login(self.recruiter)
        url = reverse('candidate_notes_api', kwargs={'job_id': self.job.id, 'candidate_id': self.screening1.id})
        response = self.client.post(
            url,
            data=json.dumps({'notes': 'Excellent problem solving skills.'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['notes'], 'Excellent problem solving skills.')

        self.screening1.refresh_from_db()
        self.assertEqual(self.screening1.recruiter_notes, 'Excellent problem solving skills.')

    def test_bulk_shortlist_api(self):
        self.client.force_login(self.recruiter)
        url = reverse('bulk_shortlist', kwargs={'job_id': self.job.id})
        response = self.client.post(
            url,
            data=json.dumps({'candidate_ids': [self.screening1.id, self.screening2.id]}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 2)

        self.screening1.refresh_from_db()
        self.screening2.refresh_from_db()
        self.assertEqual(self.screening1.status, 'shortlisted')
        self.assertEqual(self.screening2.status, 'shortlisted')

    def test_bulk_reject_api(self):
        self.client.force_login(self.recruiter)
        url = reverse('bulk_reject', kwargs={'job_id': self.job.id})
        response = self.client.post(
            url,
            data=json.dumps({'candidate_ids': [self.screening2.id]}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 1)

        self.screening2.refresh_from_db()
        self.assertEqual(self.screening2.status, 'rejected')

    def test_api_isolation_between_recruiters(self):
        self.client.force_login(self.other_recruiter)
        url = reverse('candidate_status_api', kwargs={'job_id': self.job.id, 'candidate_id': self.screening1.id})
        response = self.client.post(
            url,
            data=json.dumps({'status': 'shortlisted'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)

    def test_superuser_access_to_api(self):
        self.client.force_login(self.superuser)
        url = reverse('candidate_status_api', kwargs={'job_id': self.job.id, 'candidate_id': self.screening1.id})
        response = self.client.post(
            url,
            data=json.dumps({'status': 'rejected'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.screening1.refresh_from_db()
        self.assertEqual(self.screening1.status, 'rejected')

