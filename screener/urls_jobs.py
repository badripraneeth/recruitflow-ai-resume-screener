from django.urls import path
from screener import views

app_name = 'jobs'

urlpatterns = [
    path('', views.job_list_view, name='job_list'),
    path('create/', views.job_create_view, name='job_create'),
    path('<int:job_id>/', views.job_detail_view, name='job_detail'),
]
