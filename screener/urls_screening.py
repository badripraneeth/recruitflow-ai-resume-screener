from django.urls import path
from screener import views

app_name = 'screening'

urlpatterns = [
    path('candidates/', views.candidate_list_view, name='candidates'),
    path('jobs/<int:job_id>/candidates/', views.candidate_list_view, name='job_candidates'),
    path('candidates/<int:candidate_id>/', views.candidate_detail_view, name='candidate_detail'),
    path('candidates/<int:candidate_id>/decision/', views.candidate_decision_view, name='candidate_decision'),
    path('candidates/<int:candidate_id>/notes/', views.candidate_notes_view, name='candidate_notes'),
    path('shortlisted/', views.shortlisted_view, name='shortlisted'),
]
