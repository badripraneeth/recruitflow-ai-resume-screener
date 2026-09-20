from django.contrib import admin
from .models import Job, ScreeningResult


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'recruiter',
        'status',
        'min_experience',
        'max_experience',
        'minimum_score',
        'shortlist_count',
        'created_at'
    )
    list_filter = ('status', 'created_at', 'recruiter')
    search_fields = ('title', 'description', 'recruiter__email')
    ordering = ('-created_at',)


@admin.register(ScreeningResult)
class ScreeningResultAdmin(admin.ModelAdmin):
    list_display = (
        'resume',
        'job',
        'total_score',
        'required_skills_score',
        'preferred_skills_score',
        'experience_score',
        'education_score',
        'projects_score',
        'screened_at'
    )
    list_filter = ('job', 'screened_at')
    search_fields = ('resume__candidate_name', 'resume__candidate_email', 'job__title')
    readonly_fields = (
        'required_skills_score',
        'preferred_skills_score',
        'experience_score',
        'education_score',
        'projects_score',
        'total_score',
        'screened_at'
    )
