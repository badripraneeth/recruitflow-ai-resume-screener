from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ai.matching import analyze_resume_against_job
from screener.models import Job, ScreeningResult
from screening.services.scoring import apply_scoring_to_screening_result
from .forms import ResumeUploadForm
from .models import Resume
from .services import extract_text_from_pdf


@login_required
def resume_upload_view(request, job_id=None):
    initial_job = None
    if job_id:
        initial_job = get_object_or_404(Job, id=job_id, recruiter=request.user)

    if request.method == 'POST':
        files = request.FILES.getlist('resumes') or request.FILES.getlist('resume')
        target_job_id = request.POST.get('job_id') or request.POST.get('job') or (initial_job.id if initial_job else None)
        if request.user.is_superuser:
            target_job = get_object_or_404(Job, id=target_job_id)
        else:
            target_job = get_object_or_404(Job, id=target_job_id, recruiter=request.user)

        if not files:
            messages.error(request, 'Please select at least one resume file to upload.')
        else:
            success_count = 0
            for file_obj in files:
                ext = file_obj.name.split('.')[-1].lower()
                if ext not in ('pdf', 'docx'):
                    continue

                # Save Resume record
                resume = Resume.objects.create(
                    recruiter=request.user,
                    job=target_job,
                    file=file_obj,
                    candidate_name=file_obj.name.rsplit('.', 1)[0]
                )

                # Extract text
                extracted_text = ""
                try:
                    extracted_text = extract_text_from_pdf(resume.file.path)
                except Exception:
                    try:
                        extracted_text = extract_text_from_pdf(file_obj)
                    except Exception:
                        extracted_text = ""

                resume.extracted_text = extracted_text or "Resume text extraction completed."
                resume.save(update_fields=['extracted_text'])

                # Run AI Matching & Deterministic Scoring
                try:
                    screening_res, analysis = analyze_resume_against_job(resume, target_job)
                    apply_scoring_to_screening_result(screening_res, analysis, target_job)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).exception("Screening error for resume %s: %s", resume.id, e)
                    from ai.matching import extract_fallback_analysis_from_text
                    analysis = extract_fallback_analysis_from_text(resume.extracted_text or "", target_job)
                    screening_res, _ = ScreeningResult.objects.get_or_create(
                        job=target_job,
                        resume=resume,
                        defaults={
                            'matched_required_skills': analysis.get('matched_required_skills', []),
                            'missing_required_skills': analysis.get('missing_required_skills', target_job.required_skills or []),
                            'matched_preferred_skills': analysis.get('matched_preferred_skills', []),
                            'missing_preferred_skills': analysis.get('missing_preferred_skills', target_job.preferred_skills or []),
                            'candidate_experience_years': analysis.get('experience_years', 0.0),
                            'candidate_summary': "Resume text could not be fully analyzed. Manual review recommended.",
                            'status': ScreeningResult.STATUS_REVIEW,
                        }
                    )
                    apply_scoring_to_screening_result(screening_res, analysis, target_job)
                success_count += 1

            messages.success(request, f'Successfully uploaded and screened {success_count} resumes for "{target_job.title}"!')
            return redirect('job_detail', pk=target_job.pk)
    else:
        form = ResumeUploadForm(request.user, initial={'job': initial_job})

    return render(request, 'resumes/upload.html', {
        'form': form,
        'target_job': initial_job,
    })


@login_required
def resume_analyze_view(request, pk):
    resume = get_object_or_404(Resume, pk=pk, recruiter=request.user)
    if request.method == 'POST':
        try:
            screening_res, analysis = analyze_resume_against_job(resume, resume.job)
            apply_scoring_to_screening_result(screening_res, analysis, resume.job)
            messages.success(request, 'Resume analyzed successfully.')
        except Exception as e:
            messages.error(request, f'Analysis error: {e}')
        return redirect('resume_analysis_detail', pk=resume.pk)
    return redirect('resume_analysis_detail', pk=resume.pk)


@login_required
def resume_analysis_detail_view(request, pk):
    resume = get_object_or_404(Resume, pk=pk, recruiter=request.user)
    screening = ScreeningResult.objects.filter(resume=resume).first()
    return render(request, 'resumes/analysis_detail.html', {
        'resume': resume,
        'screening': screening,
        'job': resume.job,
    })


@login_required
def resume_download_view(request, pk):
    """
    Safely serves or downloads the candidate resume PDF file.
    If the file exists on disk, streams it inline.
    If the file was removed due to cloud container ephemeral restart, returns a helpful message.
    """
    import os
    from django.http import FileResponse, Http404, HttpResponse

    if request.user.is_superuser:
        resume = get_object_or_404(Resume, pk=pk)
    else:
        resume = get_object_or_404(Resume, pk=pk, recruiter=request.user)

    if not resume.file:
        raise Http404("No file attached to this candidate resume.")

    try:
        file_path = resume.file.path
    except Exception:
        file_path = None

    if not file_path or not os.path.exists(file_path):
        return HttpResponse(
            f"<div style='font-family: sans-serif; padding: 2rem; max-width: 600px; margin: 2rem auto; border: 1px solid #cbd5e1; border-radius: 8px;'>"
            f"<h2 style='color: #e11d48;'>Resume File Not Found on Disk</h2>"
            f"<p>The original PDF for candidate <strong>{resume.candidate_name or resume.filename}</strong> is not available on this server's disk.</p>"
            f"<p style='color: #64748b;'><em>Note: On free cloud hosting containers (such as Render free tier), the disk is ephemeral and resets upon deployment or restart. All database candidate analyses and scores are preserved, but the physical PDF must be re-uploaded to be downloaded again.</em></p>"
            f"<p><a href='javascript:history.back()' style='color: #2563eb; font-weight: 600;'>&larr; Return to Candidate</a></p>"
            f"</div>",
            status=404,
            content_type="text/html"
        )

    response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    filename = os.path.basename(file_path)
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
