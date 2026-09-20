from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from screener import views as screener_views
from accounts import views as accounts_views
from resumes import views as resumes_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Dashboard
    path('', screener_views.dashboard_view, name='dashboard'),

    # Accounts
    path('login/', accounts_views.login_view, name='login'),
    path('register/', accounts_views.register_view, name='register'),
    path('logout/', accounts_views.logout_view, name='logout'),
    path('accounts/', include('accounts.urls', namespace='accounts')),

    # Jobs
    path('jobs/', screener_views.job_list_view, name='job_list'),
    path('jobs/create/', screener_views.job_create_view, name='job_create'),
    path('jobs/<int:pk>/', screener_views.job_detail_view, name='job_detail'),
    path('jobs/<int:pk>/edit/', screener_views.job_edit_view, name='job_edit'),
    path('jobs/<int:pk>/delete/', screener_views.job_delete_view, name='job_delete'),
    path('jobs/<int:job_id>/candidates/', screener_views.job_candidates_view, name='job_candidates'),
    path('jobs/<int:job_id>/upload/', screener_views.job_resume_upload_view, name='job_resume_upload'),

    # Candidates
    path('candidates/', screener_views.candidates_hub_view, name='candidates_hub'),
    path('candidates/<int:candidate_id>/', screener_views.candidate_detail_direct_view, name='candidate_detail_direct'),
    path('jobs/<int:job_id>/candidates/<int:candidate_id>/', screener_views.candidate_detail_view, name='candidate_detail'),

    # Shortlisted
    path('shortlisted/', screener_views.shortlisted_candidates_view, name='shortlisted_candidates'),
    path('jobs/<int:job_id>/shortlisted/', screener_views.shortlisted_candidates_view, name='job_shortlisted_candidates'),

    # Resumes
    path('upload/', resumes_views.resume_upload_view, name='upload'),
    path('resumes/upload/', resumes_views.resume_upload_view, name='resume_upload'),
    path('resumes/<int:pk>/analyze/', resumes_views.resume_analyze_view, name='resume_analyze'),
    path('resumes/<int:pk>/analysis/', resumes_views.resume_analysis_detail_view, name='resume_analysis_detail'),
    path('resumes/', include('resumes.urls', namespace='resumes')),

    # Decision & Bulk APIs
    path('jobs/<int:job_id>/candidates/<int:candidate_id>/status/', screener_views.candidate_status_api, name='candidate_status_api'),
    path('jobs/<int:job_id>/candidates/<int:candidate_id>/notes/', screener_views.candidate_notes_api, name='candidate_notes_api'),
    path('jobs/<int:job_id>/candidates/bulk-shortlist/', screener_views.bulk_shortlist, name='bulk_shortlist'),
    path('jobs/<int:job_id>/candidates/bulk-reject/', screener_views.bulk_reject, name='bulk_reject'),
    path('jobs/<int:job_id>/candidates/bulk-shortlist-reject-unselected/', screener_views.bulk_shortlist_reject_unselected, name='bulk_shortlist_reject_unselected'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
