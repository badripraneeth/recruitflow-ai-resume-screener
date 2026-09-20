from django.contrib import admin
from .models import Resume


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ('id', 'filename', 'job', 'recruiter', 'uploaded_at')
    list_filter = ('job', 'uploaded_at', 'recruiter')
    search_fields = ('candidate_name', 'candidate_email', 'extracted_text', 'recruiter__email')
    readonly_fields = ('uploaded_at', 'updated_at', 'extracted_text')
