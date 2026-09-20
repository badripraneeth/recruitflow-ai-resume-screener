from django import forms
from django.core.exceptions import ValidationError
from .models import Job


class JobForm(forms.ModelForm):
    required_skills_input = forms.CharField(
        label="Required Skills",
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. Python, Django, PostgreSQL',
        }),
        help_text="Enter mandatory skills separated by commas."
    )
    preferred_skills_input = forms.CharField(
        label="Preferred Skills",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. Docker, AWS, Redis, GraphQL',
        }),
        help_text="Optional: Enter nice-to-have skills separated by commas."
    )

    class Meta:
        model = Job
        fields = (
            'title',
            'status',
            'description',
            'min_experience',
            'max_experience',
            'minimum_score',
            'shortlist_count',
        )
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Senior Backend Engineer',
            }),
            'status': forms.Select(attrs={
                'class': 'form-input',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 5,
                'placeholder': 'Provide comprehensive details regarding job responsibilities, qualifications, and role expectations...',
            }),
            'min_experience': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '0',
                'step': '0.5',
                'placeholder': 'e.g. 3',
            }),
            'max_experience': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '0',
                'step': '0.5',
                'placeholder': 'e.g. 6 (Optional)',
            }),
            'minimum_score': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '0',
                'max': '100',
                'step': '1',
                'placeholder': 'e.g. 70 (Optional)',
            }),
            'shortlist_count': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '1',
                'step': '1',
                'placeholder': 'e.g. 10 (Optional)',
            }),
        }
        help_texts = {
            'min_experience': 'Minimum years of experience required.',
            'max_experience': 'Optional: Maximum years of experience threshold.',
            'minimum_score': 'Optional: Minimum qualification score (0-100). Leave empty if not required.',
            'shortlist_count': 'Optional: Target number of candidates to shortlist. Leave empty if unconstrained.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure optional fields are clearly marked as optional
        self.fields['max_experience'].required = False
        self.fields['minimum_score'].required = False
        self.fields['shortlist_count'].required = False

        # Populate comma-separated skills when editing
        if self.instance and self.instance.pk:
            if self.instance.required_skills:
                self.fields['required_skills_input'].initial = ', '.join(self.instance.required_skills)
            if self.instance.preferred_skills:
                self.fields['preferred_skills_input'].initial = ', '.join(self.instance.preferred_skills)

    def clean_required_skills_input(self):
        raw = self.cleaned_data.get('required_skills_input', '')
        skills = [s.strip() for s in raw.split(',') if s.strip()]
        if not skills:
            raise ValidationError('Please provide at least one required skill.')
        return skills

    def clean_preferred_skills_input(self):
        raw = self.cleaned_data.get('preferred_skills_input', '')
        skills = [s.strip() for s in raw.split(',') if s.strip()]
        return skills

    def clean(self):
        cleaned_data = super().clean()
        min_exp = cleaned_data.get('min_experience')
        max_exp = cleaned_data.get('max_experience')
        min_score = cleaned_data.get('minimum_score')
        shortlist_count = cleaned_data.get('shortlist_count')

        if min_exp is not None and min_exp < 0:
            self.add_error('min_experience', 'Minimum experience cannot be negative.')

        if min_exp is not None and max_exp is not None:
            if max_exp < min_exp:
                self.add_error('max_experience', 'Maximum experience must be greater than or equal to minimum experience.')

        if min_score is not None:
            if min_score < 0 or min_score > 100:
                self.add_error('minimum_score', 'Minimum score must be between 0 and 100.')

        if shortlist_count is not None and shortlist_count < 1:
            self.add_error('shortlist_count', 'Shortlist target count must be at least 1.')

        return cleaned_data

    def save(self, commit=True):
        job = super().save(commit=False)
        job.required_skills = self.cleaned_data['required_skills_input']
        job.preferred_skills = self.cleaned_data['preferred_skills_input']
        if commit:
            job.save()
        return job
