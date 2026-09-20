import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import TemplateView

from .forms import JobForm
from .models import Job, ScreeningResult
from resumes.models import Resume
from resumes.forms import ResumeUploadForm
from resumes.services.pdf_parser import extract_text_from_pdf
from ai.matching import analyze_resume_against_job
from screening.services.scoring import apply_scoring_to_screening_result


@login_required
def dashboard_view(request):
    if request.user.is_superuser:
        recruiter_jobs = Job.objects.all()
        active_jobs = recruiter_jobs.filter(status=Job.STATUS_ACTIVE).count()
        total_resumes = Resume.objects.all().count()
        in_review = ScreeningResult.objects.filter(status=ScreeningResult.STATUS_REVIEW).count()
        shortlisted = ScreeningResult.objects.filter(status=ScreeningResult.STATUS_SHORTLISTED).count()
        rejected = ScreeningResult.objects.filter(status=ScreeningResult.STATUS_REJECTED).count()
    else:
        recruiter_jobs = Job.objects.filter(recruiter=request.user)
        active_jobs = recruiter_jobs.filter(status=Job.STATUS_ACTIVE).count()
        total_resumes = Resume.objects.filter(job__recruiter=request.user).count()
        in_review = ScreeningResult.objects.filter(
            job__recruiter=request.user,
            status=ScreeningResult.STATUS_REVIEW
        ).count()
        shortlisted = ScreeningResult.objects.filter(
            job__recruiter=request.user,
            status=ScreeningResult.STATUS_SHORTLISTED
        ).count()
        rejected = ScreeningResult.objects.filter(
            job__recruiter=request.user,
            status=ScreeningResult.STATUS_REJECTED
        ).count()
    recent_jobs = recruiter_jobs.order_by('-created_at')[:5]

    context = {
        'active_jobs_count': active_jobs,
        'total_resumes': total_resumes,
        'total_resumes_count': total_resumes,
        'in_review_candidates': in_review,
        'in_review_candidates_count': in_review,
        'shortlisted_candidates': shortlisted,
        'shortlisted_candidates_count': shortlisted,
        'rejected_candidates': rejected,
        'rejected_candidates_count': rejected,
        'recent_jobs': recent_jobs,
    }
    return render(request, 'dashboard/dashboard.html', context)


@login_required
def job_list_view(request):
    if request.user.is_superuser:
        jobs = Job.objects.all().order_by('-created_at')
    else:
        jobs = Job.objects.filter(recruiter=request.user).order_by('-created_at')
    return render(request, 'jobs/job_list.html', {'jobs': jobs})


@login_required
def job_create_view(request):
    if request.method == 'POST':
        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.recruiter = request.user
            job.save()
            messages.success(request, f'Job opening "{job.title}" created successfully!')
            return redirect('job_detail', pk=job.pk)
    else:
        form = JobForm()
    return render(request, 'jobs/job_create.html', {'form': form})


@login_required
def job_detail_view(request, pk):
    if request.user.is_superuser:
        job = get_object_or_404(Job, pk=pk)
    else:
        job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    return render(request, 'jobs/job_detail.html', {'job': job})


@login_required
def job_edit_view(request, pk):
    if request.user.is_superuser:
        job = get_object_or_404(Job, pk=pk)
    else:
        job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    if request.method == 'POST':
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, f'Job opening "{job.title}" updated successfully!')
            return redirect('job_detail', pk=job.pk)
    else:
        form = JobForm(instance=job)
    return render(request, 'jobs/job_create.html', {'form': form, 'job': job, 'is_edit': True})


@login_required
def job_delete_view(request, pk):
    if request.user.is_superuser:
        job = get_object_or_404(Job, pk=pk)
    else:
        job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    if request.method == 'POST':
        job.delete()
        messages.success(request, 'Job opening deleted successfully!')
        return redirect('job_list')
    return redirect('job_detail', pk=pk)


@login_required
def job_candidates_view(request, job_id):
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, recruiter=request.user)
    candidates = list(
        ScreeningResult.objects.filter(job=job)
        .select_related('resume')
    )
    # Default ranking: final_score DESC with tie breaking
    candidates.sort(
        key=lambda c: (
            -float(c.total_score or 0.0),
            -float(c.experience_score or 0.0),
            -float(c.required_skills_score or 0.0),
            c.id
        )
    )
    for idx, c in enumerate(candidates, start=1):
        c.calculated_rank = idx

    # Search by name, email, or skills
    q = request.GET.get('q') or request.GET.get('search')
    if q:
        q_str = q.strip().lower()
        candidates = [
            c for c in candidates
            if q_str in (c.candidate_name or '').lower()
            or q_str in (c.candidate_email or '').lower()
            or any(q_str in s.lower() for s in (c.all_matched_skills + (c.matched_required_skills or []) + (c.matched_preferred_skills or [])))
        ]

    # Filter by score
    min_score = request.GET.get('min_score')
    if min_score:
        try:
            candidates = [c for c in candidates if float(c.total_score or 0.0) >= float(min_score)]
        except ValueError:
            pass

    max_score = request.GET.get('max_score')
    if max_score:
        try:
            candidates = [c for c in candidates if float(c.total_score or 0.0) <= float(max_score)]
        except ValueError:
            pass

    # Filter by experience
    experience = request.GET.get('experience') or request.GET.get('min_exp')
    if experience:
        try:
            candidates = [c for c in candidates if float(c.candidate_experience_years or 0.0) >= float(experience)]
        except ValueError:
            pass

    # Sorting
    sort_by = request.GET.get('sort')
    if sort_by == 'score_asc':
        candidates.sort(key=lambda c: (float(c.total_score or 0.0), c.id))
    elif sort_by == 'name_asc':
        candidates.sort(key=lambda c: (c.candidate_name or '').lower())
    elif sort_by == 'exp_desc':
        candidates.sort(key=lambda c: (-float(c.candidate_experience_years or 0.0), -float(c.total_score or 0.0), c.id))

    # Top-N slicing
    top_n = request.GET.get('top_n')
    if top_n:
        try:
            candidates = candidates[:int(top_n)]
        except ValueError:
            pass

    return render(request, 'screening/candidates.html', {
        'candidates': candidates,
        'selected_job': job,
        'job': job,
    })


@login_required
def candidate_detail_view(request, job_id, candidate_id):
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, recruiter=request.user)
    candidate = get_object_or_404(
        ScreeningResult.objects.select_related('resume', 'job'),
        id=candidate_id,
        job=job
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'shortlist':
            candidate.set_decision(ScreeningResult.STATUS_SHORTLISTED)
            messages.success(request, 'Candidate shortlisted successfully.')
        elif action == 'review':
            candidate.set_decision(ScreeningResult.STATUS_REVIEW)
            messages.success(request, 'Candidate moved to In Review.')
        elif action == 'reject':
            candidate.set_decision(ScreeningResult.STATUS_REJECTED)
            messages.success(request, 'Candidate rejected.')
        elif action == 'save_notes':
            notes = request.POST.get('recruiter_notes', '').strip()
            candidate.recruiter_notes = notes
            candidate.save(update_fields=['recruiter_notes'])
            if candidate.resume:
                candidate.resume.recruiter_notes = notes
                candidate.resume.save(update_fields=['recruiter_notes'])
            messages.success(request, 'Recruiter notes saved.')

        return redirect('candidate_detail', job_id=job.id, candidate_id=candidate.id)

    return render(request, 'screening/candidate_detail.html', {
        'candidate': candidate,
        'job': job,
    })


@login_required
def candidate_detail_direct_view(request, candidate_id):
    if request.user.is_superuser:
        candidate = get_object_or_404(
            ScreeningResult.objects.select_related('job'),
            id=candidate_id
        )
    else:
        candidate = get_object_or_404(
            ScreeningResult.objects.select_related('job'),
            id=candidate_id,
            job__recruiter=request.user
        )
    return redirect('candidate_detail', job_id=candidate.job.id, candidate_id=candidate.id)


@login_required
def candidates_hub_view(request):
    if request.user.is_superuser:
        active_job = Job.objects.filter(status=Job.STATUS_ACTIVE).first() or Job.objects.first()
        if active_job:
            return redirect('job_candidates', job_id=active_job.id)
    else:
        active_job = Job.objects.filter(recruiter=request.user, status=Job.STATUS_ACTIVE).first()
        if active_job:
            return redirect('job_candidates', job_id=active_job.id)
        any_job = Job.objects.filter(recruiter=request.user).first()
        if any_job:
            return redirect('job_candidates', job_id=any_job.id)
    return redirect('job_list')


@login_required
def shortlisted_candidates_view(request, job_id=None):
    if request.user.is_superuser:
        if job_id:
            job = get_object_or_404(Job, id=job_id)
            shortlisted = ScreeningResult.objects.filter(job=job, status=ScreeningResult.STATUS_SHORTLISTED)
        else:
            shortlisted = ScreeningResult.objects.filter(status=ScreeningResult.STATUS_SHORTLISTED)
    else:
        if job_id:
            job = get_object_or_404(Job, id=job_id, recruiter=request.user)
            shortlisted = ScreeningResult.objects.filter(job=job, status=ScreeningResult.STATUS_SHORTLISTED)
        else:
            shortlisted = ScreeningResult.objects.filter(job__recruiter=request.user, status=ScreeningResult.STATUS_SHORTLISTED)

    shortlisted = shortlisted.select_related('job', 'resume').order_by('-screened_at')

    if request.method == 'POST':
        action = request.POST.get('action')
        cand_id = request.POST.get('candidate_id')
        if action == 'move_to_review' and cand_id:
            cand = get_object_or_404(ScreeningResult, id=cand_id, job__recruiter=request.user)
            cand.set_decision(ScreeningResult.STATUS_REVIEW)
            messages.success(request, 'Candidate moved back to Review.')
            return redirect(request.path)

    return render(request, 'screening/shortlisted.html', {
        'shortlisted': shortlisted
    })


@login_required
def job_resume_upload_view(request, job_id):
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, recruiter=request.user)

    if request.method == 'POST':
        files = request.FILES.getlist('resumes') or request.FILES.getlist('resume')
        if not files:
            messages.error(request, 'Please select at least one resume file to upload.')
        else:
            success_count = 0
            for f in files:
                ext = f.name.split('.')[-1].lower()
                if ext not in ('pdf', 'docx'):
                    continue

                res = Resume.objects.create(
                    recruiter=request.user,
                    job=job,
                    file=f,
                    candidate_name=f.name.rsplit('.', 1)[0]
                )

                # Extract text
                text = ""
                try:
                    text = extract_text_from_pdf(res.file.path)
                except Exception:
                    try:
                        text = extract_text_from_pdf(f)
                    except Exception:
                        text = ""

                res.extracted_text = text or "Resume text extraction completed."
                res.save(update_fields=['extracted_text'])

                # Run AI Matching & Deterministic Scoring
                try:
                    sr, analysis = analyze_resume_against_job(res, job)
                    apply_scoring_to_screening_result(sr, analysis, job)
                    success_count += 1
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).exception("Failed to screen resume %s: %s", res.id, e)
                    ScreeningResult.objects.get_or_create(
                        job=job,
                        resume=res,
                        defaults={
                            'total_score': 50.0,
                            'status': ScreeningResult.STATUS_REVIEW,
                            'candidate_experience_years': job.min_experience or 1.0,
                        }
                    )

            messages.success(request, f'Successfully uploaded and screened {success_count} candidate resume(s)!')
            return redirect('job_candidates', job_id=job.id)

    form = ResumeUploadForm(request.user, initial={'job': job})
    return render(request, 'resumes/upload.html', {'form': form, 'target_job': job})


# ==============================================================================
# Pure Python / JSON APIs for Dynamic Interactions (No DRF Required!)
# ==============================================================================
@login_required
@require_http_methods(['PATCH', 'POST'])
def candidate_status_api(request, job_id, candidate_id):
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, recruiter=request.user)
    candidate = get_object_or_404(ScreeningResult, id=candidate_id, job=job)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        body = request.POST

    new_status = body.get('status')
    if new_status:
        candidate.set_decision(new_status)
    return JsonResponse({
        'status': candidate.status,
        'status_display': candidate.get_status_display(),
        'candidate_id': candidate.id,
        'candidate_name': candidate.candidate_name,
        'success': True
    })


@login_required
@require_http_methods(['PATCH', 'POST'])
def candidate_notes_api(request, job_id, candidate_id):
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, recruiter=request.user)
    candidate = get_object_or_404(ScreeningResult, id=candidate_id, job=job)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        body = request.POST

    notes = body.get('notes') or body.get('recruiter_notes') or ''
    candidate.recruiter_notes = notes
    candidate.save(update_fields=['recruiter_notes'])
    if candidate.resume:
        candidate.resume.recruiter_notes = notes
        candidate.resume.save(update_fields=['recruiter_notes'])
    return JsonResponse({'notes': candidate.recruiter_notes, 'success': True})


@login_required
@require_POST
def bulk_shortlist(request, job_id):
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, recruiter=request.user)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        body = request.POST

    cids = body.get('candidate_ids', [])
    updated = []
    for c in ScreeningResult.objects.filter(job=job, id__in=cids):
        c.set_decision(ScreeningResult.STATUS_SHORTLISTED)
        updated.append(c.id)
    return JsonResponse({'success': True, 'count': len(updated), 'updated_ids': updated})


@login_required
@require_POST
def bulk_reject(request, job_id):
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, recruiter=request.user)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        body = request.POST

    cids = body.get('candidate_ids', [])
    updated = []
    for c in ScreeningResult.objects.filter(job=job, id__in=cids):
        c.set_decision(ScreeningResult.STATUS_REJECTED)
        updated.append(c.id)
    return JsonResponse({'success': True, 'count': len(updated), 'updated_ids': updated})


@login_required
@require_POST
def bulk_shortlist_reject_unselected(request, job_id):
    if request.user.is_superuser:
        job = get_object_or_404(Job, id=job_id)
    else:
        job = get_object_or_404(Job, id=job_id, recruiter=request.user)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        body = request.POST

    selected_ids = body.get('selected_ids', [])
    visible_ids = body.get('visible_ids', [])

    # Selected -> Shortlist
    for c in ScreeningResult.objects.filter(job=job, id__in=selected_ids):
        c.set_decision(ScreeningResult.STATUS_SHORTLISTED)

    # Unselected within filter -> Reject
    unselected = [i for i in visible_ids if i not in selected_ids]
    for c in ScreeningResult.objects.filter(job=job, id__in=unselected):
        c.set_decision(ScreeningResult.STATUS_REJECTED)

    return JsonResponse({'success': True})
