import hashlib

from resumes.models import Resume


def _uploaded_file_digest(uploaded_file):
    digest = hashlib.sha256()
    uploaded_file.seek(0)
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


def find_existing_resume(recruiter, job, uploaded_file, candidate_email=''):
    """Find an existing resume for the same recruiter/job by file content or email."""
    uploaded_digest = _uploaded_file_digest(uploaded_file)
    resumes = Resume.objects.filter(recruiter=recruiter, job=job).order_by('-uploaded_at')

    for resume in resumes:
        if not resume.file:
            continue
        try:
            digest = hashlib.sha256()
            with resume.file.open('rb') as existing_file:
                for chunk in iter(lambda: existing_file.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() == uploaded_digest:
                return resume
        except (OSError, ValueError):
            continue

    if candidate_email:
        return resumes.filter(candidate_email__iexact=candidate_email).first()
    return None


def remove_duplicate_resumes(resume, candidate_email):
    """Keep one resume record per recruiter, job, and extracted candidate email."""
    if not candidate_email:
        return

    duplicates = Resume.objects.filter(
        recruiter=resume.recruiter,
        job=resume.job,
        candidate_email__iexact=candidate_email,
    ).exclude(pk=resume.pk)

    for duplicate in duplicates:
        if duplicate.file and duplicate.file.name != resume.file.name:
            duplicate.file.delete(save=False)
        duplicate.delete()
