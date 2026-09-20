from django import forms
from screener.models import Job


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'class': 'form-input', 'accept': '.pdf,.docx'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class ResumeUploadForm(forms.Form):
    job = forms.ModelChoiceField(
        queryset=Job.objects.none(),
        required=True,
        empty_label='-- Select Target Job Opening --',
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    resumes = MultipleFileField(
        required=True,
        help_text='Upload one or more PDF or DOCX candidate resumes.'
    )

    def __init__(self, recruiter=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if recruiter:
            self.fields['job'].queryset = Job.objects.filter(recruiter=recruiter, status=Job.STATUS_ACTIVE)
