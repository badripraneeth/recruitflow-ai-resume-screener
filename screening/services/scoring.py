"""
Deterministic Candidate Scoring Engine.
Calculates candidate match scores (0-100) using a strict weighted rubric:
  - Required Skills:  40%
  - Preferred Skills: 15%
  - Experience:       20%
  - Education:        10%
  - Projects:         15%
  - Total:           100%

All scores are strictly calculated by this Python engine, NEVER by the LLM.
Every newly screened candidate is guaranteed to have status = "review".
"""

import math


class DeterministicScoringEngine:
    """
    Mathematical scoring engine that evaluates structured candidate data against job requirements.
    Guarantees:
      - 100% deterministic calculation
      - Final score strictly clamped between 0.0 and 100.0
      - Transparent breakdown of every component
      - Preserves candidate status as 'review' (no automatic shortlist or reject)
    """

    # Default Category Weights
    WEIGHT_REQUIRED_SKILLS = 40.0
    WEIGHT_PREFERRED_SKILLS = 15.0
    WEIGHT_EXPERIENCE = 20.0
    WEIGHT_EDUCATION = 10.0
    WEIGHT_PROJECTS = 15.0

    def __init__(
        self,
        weight_required_skills=WEIGHT_REQUIRED_SKILLS,
        weight_preferred_skills=WEIGHT_PREFERRED_SKILLS,
        weight_experience=WEIGHT_EXPERIENCE,
        weight_education=WEIGHT_EDUCATION,
        weight_projects=WEIGHT_PROJECTS
    ):
        self.weight_required = float(weight_required_skills)
        self.weight_preferred = float(weight_preferred_skills)
        self.weight_experience = float(weight_experience)
        self.weight_education = float(weight_education)
        self.weight_projects = float(weight_projects)

        # Validate total weight equals 100.0
        total_weight = (
            self.weight_required
            + self.weight_preferred
            + self.weight_experience
            + self.weight_education
            + self.weight_projects
        )
        if not math.isclose(total_weight, 100.0, rel_tol=1e-5):
            raise ValueError(f"Scoring weights must sum to 100.0, received {total_weight}")

    def calculate_required_skills_score(self, matched_skills, missing_skills, job_skills=None):
        """
        Calculates score for required mandatory skills (Max 40.0 pts).
        """
        matched_count = len(matched_skills) if matched_skills else 0
        missing_count = len(missing_skills) if missing_skills else 0

        if job_skills is not None:
            total_required = len(job_skills)
        else:
            total_required = matched_count + missing_count

        if total_required <= 0:
            # If job has no required skills, give full credit for this component
            return self.weight_required

        ratio = matched_count / total_required
        score = round(ratio * self.weight_required, 2)
        return max(0.0, min(score, self.weight_required))

    def calculate_preferred_skills_score(self, matched_skills, missing_skills, job_skills=None):
        """
        Calculates score for preferred bonus skills (Max 15.0 pts).
        """
        matched_count = len(matched_skills) if matched_skills else 0
        missing_count = len(missing_skills) if missing_skills else 0

        if job_skills is not None:
            total_preferred = len(job_skills)
        else:
            total_preferred = matched_count + missing_count

        if total_preferred <= 0:
            # If job has no preferred skills specified, full credit (not penalized)
            return self.weight_preferred

        ratio = matched_count / total_preferred
        score = round(ratio * self.weight_preferred, 2)
        return max(0.0, min(score, self.weight_preferred))

    def calculate_experience_score(self, candidate_years, min_years=0.0, max_years=None):
        """
        Calculates score for professional experience match (Max 20.0 pts).
        """
        try:
            cand_exp = float(candidate_years or 0.0)
            if cand_exp < 0:
                cand_exp = 0.0
        except (ValueError, TypeError):
            cand_exp = 0.0

        try:
            req_min = float(min_years or 0.0)
            if req_min < 0:
                req_min = 0.0
        except (ValueError, TypeError):
            req_min = 0.0

        if req_min <= 0:
            # Entry-level / no minimum requirement
            return self.weight_experience

        if cand_exp >= req_min:
            # Meets or exceeds minimum required experience
            return self.weight_experience

        # Partial credit proportional to required experience
        ratio = cand_exp / req_min
        score = round(ratio * self.weight_experience, 2)
        return max(0.0, min(score, self.weight_experience))

    def calculate_education_score(self, education_entries):
        """
        Calculates score for educational background (Max 10.0 pts).
        """
        if not education_entries:
            return 0.0

        best_score = 0.0

        # Normalization helper
        def parse_entry(entry):
            if isinstance(entry, dict):
                return (entry.get('degree') or "").lower(), (entry.get('field') or "").lower()
            return str(entry).lower(), ""

        for item in education_entries:
            degree_str, field_str = parse_entry(item)
            combined = f"{degree_str} {field_str}".strip()

            # Technical disciplines
            is_stem = any(f in combined for f in (
                'computer', 'software', 'data', 'information', 'it', 'engineer', 'math', 'science', 'tech'
            ))

            # Degree hierarchy
            if any(d in combined for d in ('phd', 'ph.d', 'doctorate', 'master', 'm.tech', 'm.s.', 'ms', 'mca', 'mba')):
                entry_score = 10.0
            elif any(d in combined for d in ('bachelor', 'b.tech', 'b.e.', 'b.s.', 'bs', 'bca', 'b.sc')):
                entry_score = 10.0 if is_stem else 8.5
            elif any(d in combined for d in ('diploma', 'associate', 'bootcamp', 'certificate')):
                entry_score = 7.0
            elif degree_str:
                entry_score = 6.0
            else:
                entry_score = 4.0

            if entry_score > best_score:
                best_score = entry_score

        return max(0.0, min(round(best_score, 2), self.weight_education))

    def calculate_projects_score(self, projects_entries):
        """
        Calculates score for relevant practical projects (Max 15.0 pts).
        """
        if not projects_entries:
            return 0.0

        count = len(projects_entries)
        if count == 0:
            return 0.0

        # Quality bonus for projects that have meaningful technical descriptions
        detailed_count = 0
        for proj in projects_entries:
            if isinstance(proj, dict):
                desc = proj.get('description', '') or ''
                if len(desc.strip()) > 20:
                    detailed_count += 1
            elif isinstance(proj, str) and len(proj.strip()) > 20:
                detailed_count += 1

        if count >= 2 and detailed_count >= 1:
            score = self.weight_projects  # Full 15.0 pts
        elif count >= 2:
            score = 13.0
        elif count == 1 and detailed_count >= 1:
            score = 12.0
        else:
            score = 8.0

        return max(0.0, min(round(score, 2), self.weight_projects))

    def calculate_score(self, candidate_data, job_requirements):
        """
        Main calculation interface.
        Accepts structured candidate data and job requirements.
        Returns a dictionary with complete score breakdown, bounded between 0 and 100.
        """
        # 1. Required Skills Score (40%)
        matched_required = candidate_data.get('matched_required_skills', []) or []
        missing_required = candidate_data.get('missing_required_skills', []) or []
        if 'required_skill_score' in candidate_data and candidate_data['required_skill_score'] is not None:
            required_skill_score = max(0.0, min(float(candidate_data['required_skill_score']), self.weight_required))
        else:
            job_required_skills = job_requirements.get('required_skills') if isinstance(job_requirements, dict) else getattr(job_requirements, 'required_skills', None)
            required_skill_score = self.calculate_required_skills_score(
                matched_required,
                missing_required,
                job_required_skills
            )

        # 2. Preferred Skills Score (15%)
        matched_preferred = candidate_data.get('matched_preferred_skills', []) or []
        missing_preferred = candidate_data.get('missing_preferred_skills', []) or []
        if 'preferred_skill_score' in candidate_data and candidate_data['preferred_skill_score'] is not None:
            preferred_skill_score = max(0.0, min(float(candidate_data['preferred_skill_score']), self.weight_preferred))
        else:
            job_preferred_skills = job_requirements.get('preferred_skills') if isinstance(job_requirements, dict) else getattr(job_requirements, 'preferred_skills', None)
            preferred_skill_score = self.calculate_preferred_skills_score(
                matched_preferred,
                missing_preferred,
                job_preferred_skills
            )

        # 3. Experience Score (20%)
        if 'experience_score' in candidate_data and candidate_data['experience_score'] is not None:
            experience_score = max(0.0, min(float(candidate_data['experience_score']), self.weight_experience))
        else:
            cand_exp = candidate_data.get('experience_years', 0.0)
            min_exp = (
                job_requirements.get('min_experience', 0.0)
                if isinstance(job_requirements, dict)
                else getattr(job_requirements, 'min_experience', 0.0)
            ) if job_requirements else 0.0
            max_exp = (
                job_requirements.get('max_experience')
                if isinstance(job_requirements, dict)
                else getattr(job_requirements, 'max_experience', None)
            ) if job_requirements else None
            experience_score = self.calculate_experience_score(cand_exp, min_exp, max_exp)

        # 4. Education Score (10%)
        if 'education_score' in candidate_data and candidate_data['education_score'] is not None:
            education_score = max(0.0, min(float(candidate_data['education_score']), self.weight_education))
        else:
            education_list = candidate_data.get('education', []) or []
            education_score = self.calculate_education_score(education_list)

        # 5. Projects Score (15%)
        if 'project_score' in candidate_data and candidate_data['project_score'] is not None:
            project_score = max(0.0, min(float(candidate_data['project_score']), self.weight_projects))
        else:
            projects_list = candidate_data.get('projects', []) or []
            project_score = self.calculate_projects_score(projects_list)

        # Final Total Score (Sum of 5 components)
        raw_final = required_skill_score + preferred_skill_score + experience_score + education_score + project_score
        final_score = max(0.0, min(round(raw_final, 2), 100.0))

        return {
            'required_skill_score': required_skill_score,
            'preferred_skill_score': preferred_skill_score,
            'experience_score': experience_score,
            'education_score': education_score,
            'project_score': project_score,
            'final_score': final_score,
            'matched_required_skills': matched_required,
            'missing_required_skills': missing_required,
            'matched_preferred_skills': matched_preferred,
            'missing_preferred_skills': missing_preferred,
            'status': 'review',  # Specification: Every candidate MUST start as 'review'
        }


def apply_scoring_to_screening_result(screening_result, candidate_data=None, job=None):
    """
    Applies the deterministic scoring engine to a ScreeningResult instance and persists the scores.
    Also ensures candidate/resume status strictly remains 'review'.
    """
    engine = DeterministicScoringEngine()

    target_job = job or screening_result.job
    data = candidate_data or screening_result.raw_ai_analysis

    # Fallback to model fields if raw_ai_analysis is empty
    if not data:
        data = {
            'matched_required_skills': screening_result.matched_required_skills,
            'missing_required_skills': screening_result.missing_required_skills,
            'matched_preferred_skills': screening_result.matched_preferred_skills,
            'missing_preferred_skills': screening_result.missing_preferred_skills,
            'experience_years': screening_result.candidate_experience_years,
            'education': screening_result.candidate_education_json,
            'projects': screening_result.candidate_projects_json,
        }

    score_data = engine.calculate_score(data, target_job)

    # Persist scores to ScreeningResult
    screening_result.required_skills_score = score_data['required_skill_score']
    screening_result.preferred_skills_score = score_data['preferred_skill_score']
    screening_result.experience_score = score_data['experience_score']
    screening_result.education_score = score_data['education_score']
    screening_result.projects_score = score_data['project_score']
    screening_result.total_score = score_data['final_score']

    # Update matched and missing skills if present in data
    update_fields = [
        'required_skills_score',
        'preferred_skills_score',
        'experience_score',
        'education_score',
        'projects_score',
        'total_score'
    ]

    if score_data.get('matched_required_skills') is not None:
        screening_result.matched_required_skills = score_data['matched_required_skills']
        update_fields.append('matched_required_skills')
    if score_data.get('missing_required_skills') is not None:
        screening_result.missing_required_skills = score_data['missing_required_skills']
        update_fields.append('missing_required_skills')
    if score_data.get('matched_preferred_skills') is not None:
        screening_result.matched_preferred_skills = score_data['matched_preferred_skills']
        update_fields.append('matched_preferred_skills')
    if score_data.get('missing_preferred_skills') is not None:
        screening_result.missing_preferred_skills = score_data['missing_preferred_skills']
        update_fields.append('missing_preferred_skills')

    screening_result.save(update_fields=update_fields)

    # Ensure Resume status remains 'review'
    if screening_result.resume and hasattr(screening_result.resume, 'status'):
        if screening_result.resume.status != 'review':
            screening_result.resume.status = 'review'
            screening_result.resume.save(update_fields=['status'])

    return score_data
