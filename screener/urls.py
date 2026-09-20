from django.urls import path
from . import views

app_name = 'screener'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('jobs/', views.job_list_view, name='job_list'),
    path('jobs/create/', views.job_create_view, name='job_create'),
    path('jobs/<int:job_id>/', views.job_detail_view, name='job_detail'),
    path('jobs/<int:job_id>/candidates/', views.candidate_list_view, name='job_candidates'),
    path('candidates/', views.candidate_list_view, name='candidates'),
    path('candidates/<int:candidate_id>/', views.candidate_detail_view, name='candidate_detail'),
    path('candidates/<int:candidate_id>/decision/', views.candidate_decision_view, name='candidate_decision'),
    path('candidates/<int:candidate_id>/notes/', views.candidate_notes_view, name='candidate_notes'),
    path('shortlisted/', views.shortlisted_view, name='shortlisted'),
]
