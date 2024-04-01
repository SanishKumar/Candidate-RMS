# applications/forms.py
from django import forms
from .models import *
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q, F
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class JobApplicationForm(forms.ModelForm):
    ph_num = PhoneNumberField()
    available_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = JobApplication
        fields = '__all__'
        exclude = ['user', 'job', 'slug']

    def __init__(self, *args, **kwargs):
        super(JobApplicationForm, self).__init__(*args, **kwargs)
        
        # Make email and username readonly
        self.fields['email'].widget.attrs['readonly'] = True
        self.fields['username'].widget.attrs['readonly'] = True

class JobForm(forms.ModelForm):
    job_release_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    job_closing_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    class Meta:
        model = Job
        exclude = ['released_by']  

    def __init__(self, *args, **kwargs):
        super(JobForm, self).__init__(*args, **kwargs)

    
class ScheduleMeetingForm(forms.ModelForm):
    job_application = forms.CharField(widget=forms.HiddenInput(), required=False)
    scheduled_meet_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    scheduled_meet_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    scheduled_meet_attendees = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(
             Q(profile__is_teamlead=True) | Q(profile__is_teamMember=True) 
        ),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    class Meta:
        model = MeetingSchedule
        fields = ['scheduled_meet_date', 'scheduled_meet_time', 'scheduled_meet_link', 'scheduled_meet_attendees']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(ScheduleMeetingForm, self).__init__(*args, **kwargs)

        if user:
            self.fields['job_application'].initial = f"{user.first_name} {user.last_name}"
            self.fields['job_application'].widget.attrs['readonly'] = True
            
            

class RejectionDetailsForm(forms.ModelForm):
    class Meta:
        model = RejectionDetails
        fields = ['title_of_rejection','reason']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4}),
        }

class AcceptanceDetailsForm(forms.ModelForm):
    class Meta:
        model = AcceptanceDetails
        fields = ['title_of_acceptance','reason']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4}),
        }

class MeetingReviewForm(forms.ModelForm):
    class Meta:
        model = MeetingReview
        fields = ['decision', 'reason']
        widgets = {
            'decision': forms.RadioSelect(choices=[('accept', 'Accept'), ('reject', 'Reject')]),
            'reason': forms.Textarea(attrs={'rows': 4}),
        }


class ManagerDecisionForm(forms.ModelForm):
    decision_choices = [
        ('accept_with_meeting', 'Accept with Meeting'),

    ]

    decision = forms.ChoiceField(
        choices=decision_choices,
        widget=forms.RadioSelect(),
        required=True,
    )

    class Meta:
        model = ManagerMainHrDecision
        fields = ['decision', 'meeting_link', 'meeting_date', 'meeting_time']

        widgets = {
            'meeting_link': forms.URLInput(attrs={'placeholder': 'Enter the meeting link'}),
            'meeting_date': forms.DateInput(attrs={'type': 'date'}),
            'meeting_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class EmailForm(forms.Form):
    subject = forms.CharField(max_length=255)
    message = forms.CharField(widget=forms.Textarea)

class UserCalendarSettingsForm(forms.ModelForm):
    
    class Meta:
        model = UserCalendarSettings
        exclude = ['user']

class CalendarEventForm(forms.ModelForm):
    class Meta:
        model = CalendarEvent
        fields = ['title', 'link', 'start', 'end', 'duration_minutes', 'unique_url']

        widgets = {
            'start': forms.DateInput(attrs={'type': 'date'}),
            'end': forms.DateInput(attrs={'type': 'time'}),
        }
    