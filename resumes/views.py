import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ai.matching import analyze_resume_against_job
from screener.models import Job, ScreeningResult
from screener.services.scoring import apply_scoring_to_screening_result
from .forms import ResumeUploadForm
from .models import Resume
from .services.duplicates import find_existing_resume, remove_duplicate_resumes
from .services.pdf_parser import PDFParsingError, PDFValidationError, extract_text_from_resume


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
                    messages.error(request, f'"{file_obj.name}" is not a supported resume format. Upload PDF or DOCX files.')
                    continue

                try:
                    extracted_text = extract_text_from_resume(file_obj)
                except (PDFValidationError, PDFParsingError) as error:
                    messages.error(request, f'Could not read "{file_obj.name}": {error}')
                    continue
                if not extracted_text.strip():
                    messages.error(request, f'No readable text was found in "{file_obj.name}". Upload a text-based PDF or DOCX.')
                    continue

                email_match = re.search(
                    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                    extracted_text,
                )
                candidate_email = email_match.group(0) if email_match else ''
                resume = find_existing_resume(request.user, target_job, file_obj, candidate_email)
                if resume is None:
                    resume = Resume.objects.create(
                        recruiter=request.user,
                        job=target_job,
                        file=file_obj,
                        candidate_name=file_obj.name.rsplit('.', 1)[0],
                        extracted_text=extracted_text,
                    )
                else:
                    resume.file.delete(save=False)
                    resume.file = file_obj
                    resume.candidate_name = ''
                    resume.candidate_email = ''
                    resume.extracted_text = extracted_text
                    resume.status = Resume.STATUS_REVIEW
                    resume.recruiter_notes = ''
                    resume.save(update_fields=[
                        'file', 'candidate_name', 'candidate_email', 'extracted_text',
                        'status', 'recruiter_notes', 'updated_at',
                    ])
                    ScreeningResult.objects.filter(job=target_job, resume=resume).delete()

                remove_duplicate_resumes(resume, candidate_email)

                # Run AI Matching & Deterministic Scoring
                try:
                    screening_res, analysis = analyze_resume_against_job(resume, target_job)
                    apply_scoring_to_screening_result(screening_res, analysis, target_job)
                except Exception as error:
                    import logging
                    logging.getLogger(__name__).exception("Screening error for resume %s: %s", resume.id, error)
                    messages.error(request, f'Could not analyze "{file_obj.name}": {error}')
                    continue
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
            if resume.file:
                extracted_text = extract_text_from_resume(resume.file)
                if not extracted_text.strip():
                    raise PDFParsingError("No readable text was found in the uploaded file.")
                resume.extracted_text = extracted_text
                resume.save(update_fields=['extracted_text', 'updated_at'])
            screening_res, analysis = analyze_resume_against_job(resume, resume.job)
            apply_scoring_to_screening_result(screening_res, analysis, resume.job)
            messages.success(request, 'Resume re-analyzed successfully.')
        except (PDFParsingError, PDFValidationError, ValueError) as error:
            messages.error(request, f'Analysis error: {error}')
        except Exception as error:
            import logging
            logging.getLogger(__name__).exception("Re-analysis failed for resume %s: %s", resume.id, error)
            messages.error(request, 'Analysis failed. Check the server logs for details.')
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
