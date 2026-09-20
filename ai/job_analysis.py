"""
Job analysis helper module.
Extracts and structures job requirements to feed into the LLM context.
"""

def prepare_job_context(job):
    """
    Extracts and standardizes job specifications from a Job model instance or dict.
    Returns a dict formatted for prompt interpolation.
    """
    if hasattr(job, 'title'):
        title = job.title or "Untitled Role"
        description = job.description or ""
        required_skills = job.required_skills or []
        preferred_skills = job.preferred_skills or []
        min_exp = getattr(job, 'min_experience', 0.0)
        max_exp = getattr(job, 'max_experience', None)
    elif isinstance(job, dict):
        title = job.get('title', 'Untitled Role')
        description = job.get('description', '')
        required_skills = job.get('required_skills', [])
        preferred_skills = job.get('preferred_skills', [])
        min_exp = job.get('min_experience', 0.0)
        max_exp = job.get('max_experience')
    else:
        raise ValueError("Invalid job object provided for context extraction.")

    # Format skills as clean comma-separated lists for prompt clarity
    req_str = ", ".join(required_skills) if required_skills else "None specified"
    pref_str = ", ".join(preferred_skills) if preferred_skills else "None specified"
    max_exp_str = f"{max_exp:g}" if max_exp is not None else "No upper bound"

    return {
        'job_title': title.strip(),
        'job_description': description.strip(),
        'required_skills': req_str,
        'preferred_skills': pref_str,
        'min_experience': f"{min_exp:g}",
        'max_experience': max_exp_str,
        'raw_required_skills': required_skills,
        'raw_preferred_skills': preferred_skills,
    }
