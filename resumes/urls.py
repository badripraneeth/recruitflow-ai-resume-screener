from django.urls import path
from . import views

app_name = 'resumes'

urlpatterns = [
    path('upload/', views.resume_upload_view, name='upload'),
    path('upload/', views.resume_upload_view, name='resume_upload'),
    path('jobs/<int:job_id>/upload/', views.resume_upload_view, name='job_upload'),
    path('<int:pk>/analyze/', views.resume_analyze_view, name='resume_analyze'),
    path('<int:pk>/analysis/', views.resume_analysis_detail_view, name='resume_analysis_detail'),
]
