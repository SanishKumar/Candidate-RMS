from django.views.generic import View
from django.views import generic
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count
from .forms import *
from .models import *
import json



class home(View):
    template_name = 'home.html'

    def get(self, request):
        return render(request, self.template_name)

class AllJobs(generic.ListView):
    model = Job
    template_name = 'all_jobs.html'
    context_object_name = 'jobs'
    
class JobDetail(generic.DetailView):
    model = Job
    template_name = 'job_detail.html'
    context_object_name = 'job'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_has_applied = False
        if self.request.user.is_authenticated:
            user_has_applied = JobApplication.objects.filter(user=self.request.user, job=context['job']).exists()
        context['user_has_applied'] = user_has_applied
        return context
    
class ApplyNowView(LoginRequiredMixin, View):
    login_url = '/accounts/login/'

    def get(self, request, job_id):
        job = Job.objects.get(pk=job_id)
        user = request.user
        initial_data = {'user': user, 'username': user.username, 'email': user.email}
        form = JobApplicationForm(initial=initial_data)
        return render(request, 'apply.html', {'form': form, 'job': job})

    def post(self, request, job_id):
        
        job = Job.objects.get(pk=job_id)
        form = JobApplicationForm(request.POST, request.FILES)
        
        if form.is_valid():
            user = request.user
            job_application = form.save(commit=False)
            job_application.user = request.user
            job_application.job = job
            job_application.logs = timezone.localtime(timezone.now())
            existing_logsjson = job_application.logsjson
            existing_logs_dict = json.loads(existing_logsjson) if existing_logsjson else {}
            new_data ={
                "student": ["applied", {"applied_on": str(timezone.localtime(timezone.now()))}], "open_count": 1, "base_hr":{"open1":["username","recent_date","viewed_on","status"] }
            }
            existing_logs_dict.update(new_data)
            job_application.logsjson = json.dumps(existing_logs_dict)
            job_application.save()
            return redirect('all_jobs')
            
        return render(request, 'apply.html', {'form': form, 'job': job})

class AppliedJobs(LoginRequiredMixin, View):
    template_name = 'applied_jobs.html'

    def get(self, request):
        user = request.user
        job_applications = JobApplication.objects.filter(user=user)
        application_data = []
        for application in job_applications:
            try:
                logs_data = json.loads(application.logsjson)
                status = logs_data['student'][0]
                applied_on = logs_data['student'][1]['applied_on']
            except (json.JSONDecodeError, KeyError):
                status = applied_on = "N/A"

            application_data.append({
                'job_name': application.job.job_name,
                'slug': application.slug,
                'status': status,
                'applied_on': applied_on,
            })
        return render(request, self.template_name, {'job_applications': job_applications, 'application_data': application_data })

class CustomLoginView(View):
    template_name = 'registration/login.html'

    def get(self, request):
        form = AuthenticationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                job_id = request.GET.get('job_id')
                if job_id:
                    return redirect('apply', job_id=job_id)
                else:
                    return redirect('home')
        return render(request, self.template_name, {'form': form})

class CustomLogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('all_jobs')

class RegisterView(View):
    template_name = 'registration/register.html'

    def get(self, request):
        form = CustomUserCreationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('custom_login')  # Redirect to login page after registration
        return render(request, self.template_name, {'form': form})

class ReleaseJobView(View):
    template_name = 'release_job.html'

    def get(self, request):
        if not request.user.is_authenticated or not request.user.profile.is_hr:
            return redirect('home')  

        form = JobForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        if not request.user.is_authenticated or not request.user.profile.is_hr:
            return redirect('home')

        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.released_by = request.user
            job.save()
            request.user.profile.released_jobs = job
            request.user.profile.save()
            return redirect('all_jobs')  

        return render(request, self.template_name, {'form': form})

class ViewJobApplications(UserPassesTestMixin, View):
    template_name = 'view_job_applications.html'

    def test_func(self):
        return self.request.user.is_authenticated 

    def get(self, request):
        user = request.user
        job_info_with_applicants = []

        if user.profile.is_hr:
            released_jobs = Job.objects.filter(released_by=user)
        elif user.profile.is_teamlead or user.profile.is_teamMember or user.profile.is_manager or user.profile.is_mainHr or user.profile.is_onboardingHr:
            released_jobs = Job.objects.filter(released_by__profile__is_hr=True) 

        def append_job_info(job, applicants):
            job_info = {
                'job_name': job.job_name,
                'job_location': job.job_location,
                'job_type': job.get_job_type_display(),
                'slug': job.slug,
                'num_applicants': applicants.count(),
                'applicants': applicants,
            }
            job_info_with_applicants.append(job_info)

        for job in released_jobs:
            applicants = JobApplication.objects.filter(job=job)
            if applicants:
                if user.profile.is_hr:
                    append_job_info(job, applicants)
                elif user.profile.is_teamlead or user.profile.is_teamMember:
                    if applicants.filter(hr_is_accepted=True , meetscheduled_by_hr=True):
                        append_job_info(job, applicants)
                elif user.profile.is_manager:
                    if applicants.filter(teamlead_is_accepted=True):
                        append_job_info(job, applicants)
                elif user.profile.is_mainHr:
                    if applicants.filter(manager_is_accepted=True):
                        append_job_info(job, applicants)

        return render(request, self.template_name, {'jobs_with_applicants': job_info_with_applicants})

class ViewApplicants(View):
    template_name = 'view_applicants.html'

    def get(self, request, job_slug):
        user = request.user
        job = get_object_or_404(Job, slug=job_slug)
        if user.profile.is_hr:
            applicants = JobApplication.objects.filter(job=job)
            accepted_applicants = applicants.filter(acceptancedetails__accepted_by=user)
            rejection_details = RejectionDetails.objects.filter(job_application__job=job, rejected_by=user)
            rejected_applicants = [rejection.job_application for rejection in rejection_details]
            new_applicants = JobApplication.objects.filter(job=job, hr_is_accepted=False).exclude(id__in=[applicant.id for applicant in rejected_applicants])

        elif user.profile.is_teamlead:
            applicants = JobApplication.objects.filter(job=job, hr_is_accepted=True, meetscheduled_by_hr = True)
            accepted_applicants = applicants.filter(acceptancedetails__accepted_by=user)
            rejection_details = RejectionDetails.objects.filter(job_application__job=job, rejected_by=user)
            rejected_applicants = [rejection.job_application for rejection in rejection_details]
            new_applicants = applicants.filter(teamlead_is_accepted=False).exclude(id__in=[applicant.id for applicant in rejected_applicants] )
            
        elif user.profile.is_teamMember:
            applicants = JobApplication.objects.filter(job=job, hr_is_accepted=True, meetscheduled_by_hr = True)
            accepted_applicants = applicants.filter(Q(meetingschedule__meetingreview__reviewer=user) &  Q(meetingschedule__meetingreview__decision="accept"))
            rejected_applicants = applicants.filter(Q(meetingschedule__meetingreview__reviewer=user) &  Q(meetingschedule__meetingreview__decision="reject"))
            new_applicants = applicants.exclude(id__in=[applicant.id for applicant in accepted_applicants] + [applicant.id for applicant in rejected_applicants])

        elif user.profile.is_manager:
            applicants = JobApplication.objects.filter(job=job, hr_is_accepted=True, teamlead_is_accepted=True)
            accepted_applicants = applicants.filter(acceptancedetails__accepted_by=user)
            rejection_details = RejectionDetails.objects.filter(job_application__job=job, rejected_by=user)
            rejected_applicants = [rejection.job_application for rejection in rejection_details]
            new_applicants = applicants.filter(manager_is_accepted=False).exclude(id__in=[applicant.id for applicant in rejected_applicants])                       

        elif user.profile.is_mainHr:
            applicants = JobApplication.objects.filter(job=job, hr_is_accepted=True, teamlead_is_accepted=True, manager_is_accepted=True)
            accepted_applicants = applicants.filter(acceptancedetails__accepted_by=user)
            rejection_details = RejectionDetails.objects.filter(job_application__job=job, rejected_by=user)
            rejected_applicants = [rejection.job_application for rejection in rejection_details]
            new_applicants = applicants.filter(mainHr_is_accepted=False).exclude(id__in=[applicant.id for applicant in rejected_applicants])

        for applicant in rejected_applicants:
            applicant.meeting_schedule = applicant.meetingschedule_set.first() 
            rejection_details = RejectionDetails.objects.filter(job_application=applicant).first()
            applicant.rejection_details = rejection_details
            try:
                logs_dict = json.loads(applicant.logsjson)
                applicant.student_logs= logs_dict.get("student")
                applicant.base_hr_logs = logs_dict.get("base_hr")
            except json.JSONDecodeError:
                applicant.base_hr_logs = None

        if accepted_applicants:
            for applicant in accepted_applicants:
                applicant.meeting_schedule = applicant.meetingschedule_set.first() 
                acceptance_details = AcceptanceDetails.objects.filter(job_application=applicant, accepted_by=user).first()
                applicant.acceptance_details = acceptance_details
                try:
                    logs_dict = json.loads(applicant.logsjson)
                    applicant.base_hr_logs = logs_dict.get("base_hr")
                    applicant.student_logs= logs_dict.get("student")
                except json.JSONDecodeError:
                    applicant.base_hr_logs = None
        
        pending_applicants = ManagerMainHrDecision.objects.filter(applicant__job=job, scheduled_by=user)
        pending_applicants = pending_applicants.exclude(Q(applicant__in=accepted_applicants) | Q(applicant__in=rejected_applicants))
        for applicant in pending_applicants:
            pending_details = ManagerMainHrDecision.objects.filter(applicant=applicant.applicant).first()
            applicant.pending_details = pending_details
        
        reviewed_applicants = JobApplication.objects.filter(
            meetingschedule__scheduled_meet_attendees=request.user,
            meetingschedule__meetingreview__isnull=False
        ).distinct()

        if reviewed_applicants:
            for applicant in reviewed_applicants:
                applicant.meeting_schedule = applicant.meetingschedule_set.first()
           
        reviewed_by_you = JobApplication.objects.filter(
            meetingschedule__scheduled_meet_attendees=request.user,
            meetingschedule__meetingreview__isnull=False,
            meetingschedule__meetingreview__reviewer__profile__is_teamlead=True
        ).distinct()

        for applicant in reviewed_by_you:
            applicant.meeting_schedule = applicant.meetingschedule_set.first()
            applicant.has_review = applicant.meetingschedule_set.filter(meetingreview__reviewer=request.user).exists()
            if applicant.has_review:
                applicant.review = applicant.meetingschedule_set.filter(meetingreview__reviewer=request.user).first().meetingreview_set.filter(reviewer=request.user).first()        

        reviewed_by_team_member = JobApplication.objects.filter(
            meetingschedule__scheduled_meet_attendees=request.user,
            meetingschedule__meetingreview__isnull=False,
            meetingschedule__meetingreview__reviewer__profile__is_teamMember=True
        ).distinct()

        for applicant in reviewed_by_team_member:
            applicant.meeting_schedule = applicant.meetingschedule_set.first()

        final_review_list = []
        for meeting_schedule_instance in MeetingSchedule.objects.all():
            job_application = meeting_schedule_instance.job_application
            if job_application not in accepted_applicants and job_application not in rejected_applicants:
                meeting_attendees = meeting_schedule_instance.scheduled_meet_attendees.all()
                has_review = all(
                    MeetingReview.objects.filter(meeting_schedule=meeting_schedule_instance, reviewer=attendee).exists()
                    for attendee in meeting_attendees
                )

                if has_review:
                    final_review_list.append(job_application)

        for applicant in final_review_list:
            applicant.meeting_schedule = applicant.meetingschedule_set.first()

        if new_applicants:
            if user.profile.is_teamlead:
                new_applicants = new_applicants.exclude(id__in = [applicant.id for applicant in reviewed_by_you])  
            if user.profile.is_manager:
                new_applicants = new_applicants.exclude(id__in = [applicant.applicant.id for applicant in pending_applicants])
            if user.profile.is_mainHr:
                new_applicants = new_applicants.exclude(id__in = [applicant.applicant.id for applicant in pending_applicants])
            for applicant in new_applicants:
                applicant.meeting_schedule = applicant.meetingschedule_set.first()
                try:
                    logs_dict = json.loads(applicant.logsjson)
                    applicant.student_logs= logs_dict.get("student")
                    applicant.base_hr_logs = logs_dict.get("base_hr")
                except json.JSONDecodeError:
                    applicant.base_hr_logs = None

        form = ScheduleMeetingForm()
        
        context = {
            'job': job,
            'accepted_applicants': accepted_applicants,
            'rejected_applicants': rejected_applicants,
            'new_applicants': new_applicants,
            'form': form,
            'user' : user,
            'reviewed_applicants': reviewed_applicants,
            'reviewed_by_you': reviewed_by_you,
            'reviewed_by_team_member': reviewed_by_team_member,
            'final_reviewed_applicants': final_review_list,
            'pending_applicants': pending_applicants,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, job_slug):
        job = get_object_or_404(Job, slug=job_slug)
        applicants = JobApplication.objects.filter(job=job)
        form = ScheduleMeetingForm(request.POST)
        action = request.POST.get('action')

        if 'accept' in request.POST:
            job_application_slug = request.POST.get('job_application_slug')
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            form = AcceptanceDetailsForm(request.POST)
            if form.is_valid():
                acceptance_details = form.save(commit=False)
                acceptance_details.job_application = job_application
                acceptance_details.accepted_by = request.user
                job_application.teamlead_is_accepted = True
                acceptance_details.save()
                job_application.save()
                return redirect('view_applicants', job_slug=job_slug)
        
        elif 'reject' in request.POST:
            job_application_slug = request.POST.get('job_application_slug')
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            form = RejectionDetailsForm(request.POST)
            if form.is_valid():
                rejection_details = form.save(commit=False)
                rejection_details.job_application = job_application
                rejection_details.rejected_by = request.user
                rejection_details.logs = timezone.localtime(timezone.now())
                rejection_details.save()
                return redirect('view_applicants', job_slug=job_slug)
        
        elif 'reset' in request.POST:
            job_application_slug = request.POST.get('job_application_slug')
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            if job_application.rejectiondetails_set.exists():
                job_application.rejectiondetails_set.all().delete()
                return redirect('view_applicants', job_slug=job_slug)
        
        elif 'mail' in request.POST:
            job_application_slug = request.POST.get('job_application_slug')
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            form = EmailForm(request.POST)

            if form.is_valid():
                subject = form.cleaned_data['subject']
                message = form.cleaned_data['message']
                sender_name = request.user.username
                EmailLog.objects.create(
                    applicant=job_application,
                    sender_name=sender_name,
                    to_email=job_application.email,
                    subject=subject,
                    message=message
                )
                send_mail(
                    subject,
                    message,
                    'EMAIL_HOST_USER',
                    [job_application.email],
                    fail_silently=True,
                )
                return redirect('view_applicants', job_slug=job_slug)

        elif 'sendtobasehr' in request.POST:
            job_application_slug = request.POST.get('job_application_slug')
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            job_application.mainHr_to_hr = True
            job_application.save()
            return redirect('view_applicants', job_slug=job_slug)
            
        elif 'review' in request.POST:
            job_application_slug = request.POST.get('job_application_slug')
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            meeting_schedule = job_application.meetingschedule_set.first()
            form = MeetingReviewForm(request.POST)
            if form.is_valid():
                decision = form.cleaned_data['decision']
                reason = form.cleaned_data['reason']

                existing_review = meeting_schedule.meetingreview_set.filter(reviewer=request.user).first()

                if existing_review:
                    existing_review.decision = decision
                    existing_review.reason = reason
                    existing_review.save()
                else:
                    meeting_review = form.save(commit=False)
                    meeting_review.meeting_schedule = meeting_schedule
                    meeting_review.reviewer = request.user
                    meeting_review.save()

                return redirect('view_applicants', job_slug=job_slug)

        elif 'manageraccept' in request.POST:
            job_application_slug = request.POST.get('job_application_slug')
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            form = AcceptanceDetailsForm(request.POST)
            if form.is_valid():
                acceptance_details = form.save(commit=False)
                acceptance_details.job_application = job_application
                acceptance_details.accepted_by = request.user
                acceptance_details.save()
                if self.request.user.profile.is_manager:
                    job_application.manager_is_accepted = True
                elif self.request.user.profile.is_mainHr:
                    job_application.mainHr_is_accepted = True
                job_application.save()
                return redirect('view_applicants', job_slug=job_slug)

        elif 'managerreject' in request.POST:
            job_application_slug = request.POST.get('job_application_slug')
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            form = RejectionDetailsForm(request.POST)
            if form.is_valid():
                rejection_details = form.save(commit=False)
                rejection_details.job_application = job_application
                rejection_details.rejected_by = request.user
                rejection_details.logs = timezone.localtime(timezone.now())
                rejection_details.save()
                return redirect('view_applicants', job_slug=job_slug)

        if action == 'cancel_meeting':
            job_application_slug = request.POST.get('job_application')
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            meeting_schedule = MeetingSchedule.objects.filter(job_application=job_application).first()
            
            if meeting_schedule:
                meeting_schedule.delete()
                job_application.meetscheduled_by_hr = False
                send_mail(
                    f"Meeting canceled for {job_application.f_name} {job_application.l_name}",
                    f"The meeting scheduled for {job_application.f_name} {job_application.l_name} has been canceled.",
                    'EMAIL_HOST_USER',
                    [job_application.email],
                    fail_silently=True,
                )
                messages.success(request, 'Meeting canceled successfully.')
            else:
                messages.error(request, 'Meeting not found.')
            
            return redirect('view_applicants', job_slug=job_slug)
               
        elif form.is_valid():
            meeting_schedule = form.save(commit=False)
            job_application_slug = form.cleaned_data['job_application']
            job_application = get_object_or_404(JobApplication, slug=job_application_slug)
            existing_meeting = MeetingSchedule.objects.filter(job_application=job_application).first()
            if existing_meeting:
                existing_meeting.scheduled_meet_date = form.cleaned_data['scheduled_meet_date']
                existing_meeting.scheduled_meet_time = form.cleaned_data['scheduled_meet_time']
                existing_meeting.scheduled_meet_link = form.cleaned_data['scheduled_meet_link']
                existing_meeting.scheduled_meet_attendees.set(form.cleaned_data['scheduled_meet_attendees'])
                existing_meeting.save()

                send_mail(
                    f"Meeting Rescheduled for {job_application.f_name} {job_application.l_name}",
                    f"A meeting has been rescheduled for {job_application.f_name} {job_application.l_name} on {existing_meeting.scheduled_meet_date}. Please join using this link: {existing_meeting.scheduled_meet_link}",
                    'EMAIL_HOST_USER',
                    [job_application.email],
                    fail_silently=True,
                )
                attendees = existing_meeting.scheduled_meet_attendees.all()
                self.send_email_to_attendees(attendees, existing_meeting, 0)
                existing_logs_dict = json.loads(job_application.logsjson)
                existing_logs_dict["base_hr"]["open_count"] += 1
                teamleadname = ""
                list = []
                for attendee in attendees:
                    open_count = existing_logs_dict["base_hr"]["open_count"]
                    date = str(timezone.localtime(timezone.now()))
                    if attendee.profile.is_teamlead:
                        teamleadname = attendee.username
                    
                    if attendee.profile.is_teamMember:
                        teammembername = attendee.username
                        list.append(teammembername)
                recent_date = str(timezone.localtime(timezone.now())) if open_count == 1 else existing_logs_dict["base_hr"]["open"+str(open_count - 1)][1]
                viewed_on = str(timezone.localtime(timezone.now())) if open_count == 1 else existing_logs_dict["base_hr"]["open"+str(1)][2]
                status = "Viewed" if open_count == 1 else existing_logs_dict["base_hr"]["open"+str(open_count - 1)][3]
                new_data = {"open"+ str(open_count): [ self.request.user.username , recent_date, viewed_on, status ,{"meeting_on": str(timezone.localtime(timezone.now())),"meeting_mail":["Reschedule Mail Sent",date ],"forward_status":[teamleadname,date],"forward_members": list}]}
                existing_logs_dict["base_hr"].update(new_data)
                job_application.logsjson = json.dumps(existing_logs_dict)
                job_application.save()
                return redirect('view_applicants', job_slug=job.slug)
            
            else:
                # Continue with scheduling a new meeting
                meeting_schedule.job_application = job_application
                meeting_schedule.scheduled_by = request.user
                meeting_schedule.save()
                meeting_schedule.scheduled_meet_attendees.set(form.cleaned_data['scheduled_meet_attendees'])
                meeting_schedule.logs = timezone.now()
                meeting_schedule.save()
                job_application.meetscheduled_by_hr = True
                send_mail(
                    f"Meeting scheduled for {meeting_schedule.job_application.f_name} {meeting_schedule.job_application.l_name}",
                    f"A meeting has been scheduled for {meeting_schedule.job_application.f_name} "
                    f"{meeting_schedule.job_application.l_name} on {meeting_schedule.scheduled_meet_date}. "
                    f"Please join using this link: {meeting_schedule.scheduled_meet_link}",
                    'EMAIL_HOST_USER',
                    [meeting_schedule.job_application.email],
                    fail_silently=True,
                )
                attendees = meeting_schedule.scheduled_meet_attendees.all()
                self.send_email_to_attendees(attendees, meeting_schedule, 1)
                existing_logs_dict = json.loads(job_application.logsjson)
                for attendee in attendees:
                    open_count = existing_logs_dict["open_count"]
                    date = str(timezone.localtime(timezone.now()))
                    if attendee.profile.is_teamlead:
                        teamleadname = attendee.username
                    list = []
                    if attendee.profile.is_teamMember:
                        teammembername = attendee.username
                        list.append(teammembername)
                new_data = {"meeting_on": str(timezone.localtime(timezone.now())),"meeting_mail":["Schedule Mail Sent",date ],"forward_status":[teamleadname,date],"forward_members": list}
                existing_logs_dict["base_hr"]["open"+str(open_count)].append(new_data)
                job_application.logsjson = json.dumps(existing_logs_dict)
                job_application.save()
            return redirect('view_applicants', job_slug=job_slug)
        
            applicants = JobApplication.objects.filter(job=job)
        return render(request, self.template_name, {'job': job, 'applicants': applicants, 'form': form})
      
    def send_email_to_attendees(self, attendees, meeting_schedule, i ):
        from_email = 'EMAIL_HOST_USER'
        for attendee in attendees:
            to_email = attendee.email
            subject = f"Meeting scheduled for {meeting_schedule.job_application.f_name} {meeting_schedule.job_application.l_name}"
            if i == 0:
                message = f"Hi {attendee.username},\n\n" \
                      f"A meeting has been rescheduled for {meeting_schedule.job_application.f_name} " \
                      f"{meeting_schedule.job_application.l_name} on {meeting_schedule.scheduled_meet_date}. " \
                      f"Please join using this link: {meeting_schedule.scheduled_meet_link}"
            if i == 1:
                message = f"Hi {attendee.username},\n\n" \
                        f"A meeting has been scheduled for {meeting_schedule.job_application.f_name} " \
                        f"{meeting_schedule.job_application.l_name} on {meeting_schedule.scheduled_meet_date}. " \
                        f"Please join using this link: {meeting_schedule.scheduled_meet_link}"
            
            send_mail(subject, message, from_email, [to_email], fail_silently=True)
        
            
class ViewProfile(LoginRequiredMixin, View):
    template_name = 'view_profile.html'
    
    def get(self, request, applicant_slug):
        form = ManagerDecisionForm()
        job_application = get_object_or_404(JobApplication, slug=applicant_slug)
        has_decision = ManagerMainHrDecision.objects.filter(applicant=job_application, scheduled_by=request.user).exists()
        if self.request.user.profile.is_hr:
            existing_logs_dict = json.loads(job_application.logsjson)
            open_count = existing_logs_dict["open_count"]
            recent_date = str(timezone.localtime(timezone.now())) 
            
            status = "Viewed" if job_application.first_view == False  else existing_logs_dict["base_hr"]["open"+str(open_count)][3]
            
            if job_application.first_view == False:
                viewed_on = str(timezone.localtime(timezone.now()))
                job_application.first_view = True
            else:
                viewed_on = existing_logs_dict["base_hr"]["open"+str(open_count)][2]
            existing_logs_dict["base_hr"]["open"+str(open_count)][0] = self.request.user.username
            existing_logs_dict["base_hr"]["open"+str(open_count)][1] = recent_date
            existing_logs_dict["base_hr"]["open"+str(open_count)][2] = viewed_on
            existing_logs_dict["base_hr"]["open"+str(open_count)][3] = status
            
            job_application.logsjson = json.dumps(existing_logs_dict)
            job_application.save()
        return render(request, self.template_name, {'application': job_application, 'form': form, 'has_decision': has_decision})

    def post(self, request, applicant_slug):
        job_application = get_object_or_404(JobApplication, slug=applicant_slug)
        form = ManagerDecisionForm(request.POST)
        existing_logs_dict = json.loads(job_application.logsjson)
        action = request.POST.get('action')

        if action=="cancel_meeting":
            existing_detail = ManagerMainHrDecision.objects.filter(applicant=job_application, scheduled_by=request.user).first()
            if existing_detail:
                existing_detail.delete()
                return redirect('view_applicants' , job_slug=job_application.job.slug)
            
            send_mail(
                f"Meeting canceled for {job_application.user}",
                f"The meeting scheduled for {job_application.user} has been canceled.",
                'EMAIL_HOST_USER',
                [job_application.email],
                fail_silently=True,
            )

        if 'accept' in request.POST:
            form = AcceptanceDetailsForm(request.POST)
            if form.is_valid():
                if request.user.profile.is_hr:
                    if not job_application.hr_is_accepted:
                        acceptance_details = form.save(commit=False)
                        acceptance_details.job_application = job_application
                        acceptance_details.accepted_by = request.user
                        acceptance_details.save()
                        job_application.hr_is_accepted = True
                        open_count = existing_logs_dict["open_count"]
                        existing_logs_dict["base_hr"]["open"+str(open_count)][3] = "Accepted"
                        job_application.logsjson = json.dumps(existing_logs_dict)
                        job_application.save()
                        review_heading = form.cleaned_data['title_of_acceptance']
                        review_reason = form.cleaned_data['reason']
                        new_data = {"review_heading": review_heading, "review_reason": review_reason}
                        existing_logs_dict["base_hr"]["open" + str(open_count)].extend([
                            new_data["review_heading"],
                            new_data["review_reason"]
                        ])
                        job_application.logsjson = json.dumps(existing_logs_dict)
                        job_application.save()
                elif request.user.profile.is_manager:
                    if not job_application.manager_is_accepted:
                        acceptance_details = form.save(commit=False)    
                        acceptance_details.job_application = job_application
                        acceptance_details.accepted_by = request.user
                        acceptance_details.save()
                        job_application.manager_is_accepted = True
                        job_application.save() 
                elif request.user.profile.is_mainHr:
                    if not job_application.mainHr_is_accepted:
                        acceptance_details = form.save(commit=False)    
                        acceptance_details.job_application = job_application
                        acceptance_details.accepted_by = request.user
                        acceptance_details.save()
                        job_application.mainHr_is_accepted = True
                        job_application.save()
            return redirect('view_applicants' , job_slug=job_application.job.slug)

        elif 'reject' in request.POST:
            form = RejectionDetailsForm(request.POST)
            if form.is_valid():
                rejection_details = form.save(commit=False)
                rejection_details.job_application = job_application
                rejection_details.rejected_by = request.user
                rejection_details.save()
                review_heading = form.cleaned_data['title_of_rejection']
                
                review_reason = form.cleaned_data['reason']
                
                open_count = existing_logs_dict["open_count"]
                existing_logs_dict["base_hr"]["open"+str(open_count)][3] = "Rejected"
                new_data = {"review_heading": review_heading, "review_reason": review_reason}
                existing_logs_dict["base_hr"]["open" + str(open_count)].extend([
                    new_data["review_heading"],
                    new_data["review_reason"]
                ])
                job_application.logsjson = json.dumps(existing_logs_dict)
                if job_application.hr_is_accepted == True:
                    job_application.hr_is_accepted = False
                job_application.save()
                return redirect('view_applicants' , job_slug=job_application.job.slug)
        
        elif 'reset' in request.POST:
            if job_application.rejectiondetails_set.exists():
                existing_logs_dict["open_count"] += 1
                open_count = existing_logs_dict["open_count"]
                existing_logs_dict["base_hr"]["open" + str(open_count)] = ["username","recent_date","viewed_on","status"]
                job_application.first_view = False
                job_application.logsjson = json.dumps(existing_logs_dict)
                job_application.rejectiondetails_set.all().delete()
                job_application.save()
                return redirect('view_applicants' , job_slug=job_application.job.slug)
        
        elif 'givedecision' in request.POST:
            form = ManagerDecisionForm(request.POST)
            if form.is_valid():
                    decision = form.cleaned_data['decision']
                    meeting_link = form.cleaned_data.get('meeting_link', '')
                    meeting_date = form.cleaned_data.get('meeting_date', '')
                    meeting_time = form.cleaned_data.get('meeting_time', '')
                    applicant_user = User.objects.get(username=job_application.user)
                    decision_instance = ManagerMainHrDecision(
                        applicant=job_application,
                        decision=form.cleaned_data['decision'],
                        meeting_link=meeting_link,
                        meeting_date=meeting_date,
                        meeting_time=meeting_time,
                        scheduled_by=request.user,
                        email=applicant_user.email,
                    )
                    decision_instance.save()
                    if decision == 'accept_with_meeting':
                        # Send email to applicant
                        send_mail(
                            f"Meeting scheduled for {job_application.user}",
                            f"A meeting has been scheduled for {job_application.user} on {meeting_date} at {meeting_time}. "
                            f"Please join using this link: {meeting_link}",
                            'EMAIL_HOST_USER',
                            [applicant_user.email],
                            fail_silently=True,
                        )
                    return redirect('view_applicants' , job_slug=job_application.job.slug)  

        elif 'reschedule_meeting' in request.POST:
            new_meeting_date = request.POST.get('new_meeting_date')
            new_meeting_time = request.POST.get('new_meeting_time')
            existing_detail = ManagerMainHrDecision.objects.filter(applicant=job_application, scheduled_by = request.user).first()
            if existing_detail:
                existing_detail.meeting_date = new_meeting_date
                existing_detail.meeting_time = new_meeting_time
                print(existing_detail.meeting_date)  
                existing_detail.save()
                send_mail(
                    f"Meeting Rescheduled for {job_application.user}",
                    f"A meeting has been rescheduled for {job_application.user} on {new_meeting_date} at {new_meeting_time}. ",
                    'EMAIL_HOST_USER',
                    [job_application.email],
                    fail_silently=True,
                )
                return redirect('view_applicants' , job_slug=job_application.job.slug)
       

        return render(request, self.template_name, {'application': job_application, 'form': form})

class ViewScheduledMeetings(UserPassesTestMixin, View):
    template_name = 'view_scheduled_meetings.html'

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.profile.is_hr or user.profile.is_teamlead or user.profile.is_teamMember)

    def get(self, request):
        user = self.request.user
        if user.profile.is_hr:
            meetings = MeetingSchedule.objects.filter(scheduled_by=user)
        elif user.profile.is_teamlead:
            meetings = MeetingSchedule.objects.filter(scheduled_meet_attendees=user)
        elif user.profile.is_teamMember:
            meetings = MeetingSchedule.objects.filter(scheduled_meet_attendees=user)
        else:
            meetings = MeetingSchedule.objects.none()

        return render(request, self.template_name, {'meetings': meetings})
    
class ReviewMeetingView(LoginRequiredMixin, View):
    template_name = 'view_applicants.html'

    def get(self, request, applicant_slug):
        meeting = MeetingSchedule.objects.get(job_application__slug=applicant_slug)
        form = MeetingReviewForm(initial={'reviewer': request.user}) 
        has_review = meeting.meetingreview_set.filter(reviewer=request.user).exists()
        return render(request, self.template_name, {'form': form, 'meeting': meeting, 'has_review': has_review})

    def post(self, request, applicant_slug):
        meeting = MeetingSchedule.objects.get(job_application__slug=applicant_slug)
        form = MeetingReviewForm(request.POST)

        if form.is_valid():
            decision = form.cleaned_data['decision']
            reason = form.cleaned_data['reason']

            existing_review = meeting.meetingreview_set.filter(reviewer=request.user).first()

            if existing_review:
                existing_review.decision = decision
                existing_review.reason = reason
                existing_review.save()
            else:
                meeting_review = form.save(commit=False)
                meeting_review.meeting_schedule = meeting
                meeting_review.reviewer = request.user
                meeting_review.save()

            return redirect('view_applicants', job_slug=meeting.job_application.job.slug)   

        return render(request, self.template_name, {'form': form, 'meeting': meeting})

class SentByMainHr(UserPassesTestMixin, View):
    template_name = 'sent_by_mainHr.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.profile.is_hr

    def get(self, request):
        user = request.user
        job_applications = JobApplication.objects.filter(mainHr_to_hr=True)
        return render(request, self.template_name, {'job_applications': job_applications})

class CalendarSettingsView(View):
    template_name = 'home.html'

    def get(self, request, *args, **kwargs):
        print("calle")
        form = UserCalendarSettingsForm()
        
        # Fetch existing settings for the logged-in user
        existing_settings = UserCalendarSettings.objects.filter(user=request.user).first()
        if not existing_settings:
            print("No existing settings found for the user.")

        return render(request, self.template_name, {'form': form, 'existing_settings': existing_settings})
        
    def post(self, request, *args, **kwargs):
        form = UserCalendarSettingsForm(request.POST)
        if form.is_valid():
            existing_settings = UserCalendarSettings.objects.filter(user=request.user).first()

            # If existing settings exist, update them; otherwise, create new settings
            if existing_settings:
                form = UserCalendarSettingsForm(request.POST, instance=existing_settings)
            else:
                form = UserCalendarSettingsForm(request.POST)
            # print(existing_settings)
            calendar_settings = form.save(commit=False)
            calendar_settings.user = request.user
            calendar_settings.save()

            return redirect('home')  # Redirect to the same page after form submission
        return render(request, self.template_name, {'form': form})


from django.http import JsonResponse

from datetime import datetime, timedelta



class GetMyMeetingsView(View):
    def get(self, request, *args, **kwargs):
        user = self.request.user

        try:
            calendar_settings = UserCalendarSettings.objects.get(user=user)
        except UserCalendarSettings.DoesNotExist:
            calendar_settings = None

        if hasattr(user, 'profile'):
            if user.profile.is_teamlead or user.profile.is_teamMember:
                calendar_meetings = CalendarEvent.objects.filter(attendees__icontains=f'"{user.username}"')
                calendar_meetings = CalendarEvent.objects.filter(user=user) 
                schedule_meetings = MeetingSchedule.objects.filter(scheduled_meet_attendees=user)
                meetings = list(calendar_meetings) + list(schedule_meetings)
            elif user.profile.is_manager or user.profile.is_mainHr:
                manager_meetings = ManagerMainHrDecision.objects.filter(scheduled_by=user)
                calendar_meetings = CalendarEvent.objects.filter(attendees__icontains=f'"{user.username}"')
                calendar_meetings = CalendarEvent.objects.filter(user=user) 
                meetings = list(calendar_meetings) + list(manager_meetings)
            else:
                calendar_meetings = CalendarEvent.objects.filter(attendees__icontains=f'"{user.username}"')
                calendar_meetings = CalendarEvent.objects.filter(user=user) 
                meetings = list(calendar_meetings)
        else:
            schedule_meetings = MeetingSchedule.objects.filter(job_application__username=user)
            manager_meetings = ManagerMainHrDecision.objects.filter(applicant__user=user)
            calendar_meetings = CalendarEvent.objects.filter(attendees__icontains=f'"{user.username}"')
            calendar_meetings = CalendarEvent.objects.filter(user=user) 
            meetings = list(schedule_meetings) + list(manager_meetings) + list(calendar_meetings)

        events = []

        for meeting in meetings:
            if isinstance(meeting, MeetingSchedule):
                # For MeetingSchedule model
                start_datetime = datetime.combine(meeting.scheduled_meet_date, meeting.scheduled_meet_time)
                end_datetime = start_datetime + timedelta(minutes=30)

                event = {
                    'title': f"Meeting for {meeting.job_application.user.username}",
                    'start': start_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                    'end': end_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                    'url': meeting.scheduled_meet_link,
                }
            elif isinstance(meeting, ManagerMainHrDecision):
                # For ManagerMainHrDecision model
                start_datetime = datetime.combine(meeting.meeting_date, meeting.meeting_time)
                end_datetime = start_datetime + timedelta(minutes=30)

                event = {
                    'title': f"Meeting for {meeting.applicant.user.username}",
                    'start': start_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                    'end': end_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                    'url': meeting.meeting_link,
                }

            elif isinstance(meeting, CalendarEvent):
                attendees = json.loads(meeting.attendees) if meeting.attendees else []
                print(request.user, meeting.user)
                if meeting.user == request.user:  # Check if current user is the meeting creator
                    for attendee in attendees:
                        selected_date = attendee.get('selected_date', '')
                        selected_slot = attendee.get('selected_slot', '')
                        if selected_date and selected_slot:
                            event = {
                                'title': f"Meeting for {meeting.title}",
                                'start': f"{selected_date}T{selected_slot.split(' - ')[0]}",
                                'end': f"{selected_date}T{selected_slot.split(' - ')[1]}",
                                'url': meeting.link,
                            }
                            events.append(event)
                else:
                    for attendee in attendees:
                        
                        if attendee.get('name') == user.username:
                            selected_date = attendee.get('selected_date', '')
                            selected_slot = attendee.get('selected_slot', '')
                            
                            event = {
                                'title': f"Meeting for {meeting.title}",
                                'start': f"{selected_date}T{selected_slot.split(' - ')[0]}",
                                'end': f"{selected_date}T{selected_slot.split(' - ')[1]}",
                                'url': meeting.link,
                            }

            events.append(event)



        if calendar_settings:
            blocked_times = self.get_blocked_times(calendar_settings)
            events.extend(blocked_times)

        return JsonResponse({
            'events': events,  # Your existing events data
            'minTime': calendar_settings.start_time.strftime('%H:%M:%S') if calendar_settings else '08:00:00',
            'maxTime': calendar_settings.end_time.strftime('%H:%M:%S') if calendar_settings else '17:00:00',
            
        })

    def get_blocked_times(self, calendar_settings):
        blocked_times = []

        def add_blocked_time(date, start_time, end_time):
            start_datetime = datetime.combine(date, start_time)
            end_datetime = datetime.combine(date, end_time)
            i = 0 if start_time == calendar_settings.snack_break_start else 1
            blocked_times.append({
                'title': 'Snack Break' if i == 0 else 'Lunch Break',
                'start': start_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                'end': end_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                'color': 'red',  # Set color for blocked times
                'blockedTime': True,
            })
            

        current_date = datetime.now().date()
        for i in range(365):  # This example considers the next 365 days
            date = current_date + timedelta(days=i)
            add_blocked_time(date, calendar_settings.snack_break_start, calendar_settings.snack_break_end)
            add_blocked_time(date, calendar_settings.lunch_break_start, calendar_settings.lunch_break_end)

        return blocked_times
    

class CreateCalendarEventView(View):
    template_name = 'home.html'  # Replace with your template name

    def get(self, request, *args, **kwargs):
        form = CalendarEventForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = CalendarEventForm(request.POST)
        if form.is_valid():
            form.instance.user = request.user
            form.save()
            return redirect('home')  # Replace with the URL to redirect after form submission
        return render(request, self.template_name, {'form': form})


from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

@method_decorator(login_required, name='dispatch')
class SharedCalendarView(View):
    template_name = 'shared_calendar.html'

    def get(self, request, unique_url):
        calendar_event = get_object_or_404(CalendarEvent, unique_url=unique_url)

        # Get user's calendar settings and meetings
        user = calendar_event.user  # Assuming you have the user object
        duration_minutes = calendar_event.duration_minutes
        calendar_settings = UserCalendarSettings.objects.get(user=user)
        if hasattr(user, 'profile'):
            if user.profile.is_teamlead or user.profile.is_teamMember:
                calendar_meetings = CalendarEvent.objects.filter(attendees__icontains=f'"{user.username}"')
                schedule_meetings = MeetingSchedule.objects.filter(scheduled_meet_attendees=user)
                meetings = list(calendar_meetings) + list(schedule_meetings)
            elif user.profile.is_manager or user.profile.is_mainHr:
                calendar_meetings = CalendarEvent.objects.filter(attendees__icontains=f'"{user.username}"')
                manager_meetings = ManagerMainHrDecision.objects.filter(scheduled_by=user)
                meetings = list(calendar_meetings) + list(manager_meetings)
            else:
                meetings = CalendarEvent.objects.filter(attendees__icontains=f'"{user.username}"')
        else:
            schedule_meetings = MeetingSchedule.objects.filter(job_application__username=user)
            manager_meetings = ManagerMainHrDecision.objects.filter(applicant__user=user)
            calendar_meetings = CalendarEvent.objects.filter(attendees__icontains=f'"{user.username}"')
            meetings = list(schedule_meetings) + list(manager_meetings) + list(calendar_meetings)
        # meetings = MeetingSchedule.objects.filter(scheduled_meet_attendees=user)  # Get all meetings, not limited to date
        print(meetings)
        # Calculate available time slots for each date within the event's range
        available_time_slots = []
        current_date = calendar_event.start
        while current_date <= calendar_event.end:
            date_available_time_slots = self.calculate_available_time_slots_for_date(current_date, calendar_settings, meetings, duration_minutes, user)
            available_time_slots.append((current_date, date_available_time_slots))
            current_date += timedelta(days=1)


        if request.GET.get('action') == 'get_available_slots':
            date = request.GET.get('date')
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            matching_slots = [slots for date, slots in available_time_slots if date == date_obj]
            # print(matching_slots[0])
            booked_slots = self.get_booked_slots(calendar_event.attendees, date_obj)
            print(booked_slots)
            matching_slots[0] = [slot for slot in matching_slots[0] if slot not in booked_slots]
            print(matching_slots[0])
            return JsonResponse({'available_slots': matching_slots[0] if matching_slots else []})
        
        return render(request, self.template_name, {
            'start_date': calendar_event.start,
            'end_date': calendar_event.end,
            
            'calendar_event': calendar_event,
            'available_time_slots': available_time_slots,
        })

    def calculate_available_time_slots_for_date(self, date, calendar_settings, meetings, event_duration_minutes, user):
        available_time_slots = []
        current_datetime = datetime.combine(date, calendar_settings.start_time)  
        end_datetime = datetime.combine(date, calendar_settings.end_time)

        while current_datetime < end_datetime:
            start_datetime = current_datetime
            while current_datetime < end_datetime and not self.is_break_time(current_datetime.time(), calendar_settings) and not self.is_meeting_time(current_datetime.time(), meetings, date, user):
                current_datetime += timedelta(minutes=1)

            if start_datetime < current_datetime:
                slot_end_datetime = start_datetime + timedelta(minutes=event_duration_minutes)
                while slot_end_datetime <= current_datetime:
                    available_time_slots.append((start_datetime.time(), slot_end_datetime.time()))  # Extract time portions
                    start_datetime = slot_end_datetime
                    slot_end_datetime += timedelta(minutes=event_duration_minutes)

            # Advance to the end of the current break or meeting
            while self.is_break_time(current_datetime.time(), calendar_settings) or self.is_meeting_time(current_datetime.time(), meetings, date, user):
                current_datetime += timedelta(minutes=1)

        return available_time_slots

    def is_break_time(self, time, calendar_settings):
        return (
            (calendar_settings.snack_break_start <= time < calendar_settings.snack_break_end )
            or (calendar_settings.lunch_break_start <= time < calendar_settings.lunch_break_end )
        )

    # def is_meeting_time(self, time, meetings, date):
    #     return any(
    #         meeting.scheduled_meet_date == date and
    #         datetime.combine(date, meeting.scheduled_meet_time) <= datetime.combine(date, time) < datetime.combine(date, meeting.scheduled_meet_time) + timedelta(minutes=30)
    #         for meeting in meetings
    #     )
    # def is_meeting_time(self, time, meetings, date):
    #     return any(
    #         (meeting.scheduled_meet_date == date and
    #         datetime.combine(date, meeting.scheduled_meet_time) <= datetime.combine(date, time) < datetime.combine(date, meeting.scheduled_meet_time) + timedelta(minutes=30))
    #         if hasattr(meeting, 'scheduled_meet_date') and hasattr(meeting, 'scheduled_meet_time') else  # MeetingSchedule
    #         (meeting.meeting_date == date and
    #         datetime.combine(date, meeting.meeting_time) <= datetime.combine(date, time) < datetime.combine(date, meeting.meeting_time) + timedelta(minutes=30))
    #         if hasattr(meeting, 'meeting_date') and hasattr(meeting, 'meeting_time') else  # ManagerMainHrDecision
    #         (meeting.start == date and
    #         datetime.combine(date, meeting.start_time) <= datetime.combine(date, time) < datetime.combine(date, meeting.end_time))  # CalendarEvent
    #         for meeting in meetings
    #     )
    def is_meeting_time(self, time, meetings, date, user):
        return any(
            (meeting.scheduled_meet_date == date and
            datetime.combine(date, meeting.scheduled_meet_time) <= datetime.combine(date, time) < datetime.combine(date, meeting.scheduled_meet_time) + timedelta(minutes=30))
            if hasattr(meeting, 'scheduled_meet_date') and hasattr(meeting, 'scheduled_meet_time') else  # MeetingSchedule
            (meeting.meeting_date == date and
            datetime.combine(date, meeting.meeting_time) <= datetime.combine(date, time) < datetime.combine(date, meeting.meeting_time) + timedelta(minutes=30))
            if hasattr(meeting, 'meeting_date') and hasattr(meeting, 'meeting_time') else  # ManagerMainHrDecision
            (isinstance(meeting, CalendarEvent) and  # CalendarEvent
            any(
                datetime.combine(selected_date, selected_slot.split(' - ')[0]) <= datetime.combine(date, time) < datetime.combine(selected_date, selected_slot.split(' - ')[1])
                for attendee in json.loads(meeting.attendees) if attendee.get('name') == user
                for selected_date, selected_slot in attendee.items() if selected_date and selected_slot
            ))
            for meeting in meetings
        )
    
    def get_booked_slots(self, attendees_json, date):
        print(attendees_json, date) 
        attendees = json.loads(attendees_json) if attendees_json else []
        
        booked_slots = []
        for attendee in attendees:
            if attendee.get('selected_date') == str(date):
                start_time, end_time = map(lambda x: datetime.strptime(x, '%H:%M:%S').time(), attendee.get('selected_slot').split(' - '))
                booked_slots.append((start_time, end_time))
        # print(booked_slots)
        return booked_slots
    
    

class MyEvents(View):
    template_name = 'my_event.html'

    def get(self, request, *args, **kwargs):
        
        form = CalendarEventForm()
        user_events = CalendarEvent.objects.filter(user=request.user)
        return render(request, self.template_name, {'form': form, 'user_events': user_events})

    def post(self, request, *args, **kwargs):
        form = CalendarEventForm(request.POST)
        if form.is_valid():
            form.instance.user = request.user
            form.save()
            return redirect('home')  # Replace with the URL to redirect after form submission
        return render(request, self.template_name, {'form': form})


class myeventmeetings(View):
    def get(self, request, event_id, *args, **kwargs):
        meetings = CalendarEvent.objects.filter(id=event_id, user=request.user)

        

        # Create a list of events in the required format
        events = []

        for meeting in meetings:
            attendees = json.loads(meeting.attendees) if meeting.attendees else []
            print(request.user, meeting.user)
            if meeting.user == request.user:  # Check if current user is the meeting creator
                for attendee in attendees:
                    selected_date = attendee.get('selected_date', '')
                    selected_slot = attendee.get('selected_slot', '')
                    if selected_date and selected_slot:
                        event = {
                            'title': f"Meeting for {meeting.title}",
                            'start': f"{selected_date}T{selected_slot.split(' - ')[0]}",
                            'end': f"{selected_date}T{selected_slot.split(' - ')[1]}",
                            'url': meeting.link,
                        }
                        events.append(event)

        return JsonResponse({
            'events': events,
            # Include other parameters you need
        })


class BookingConfirmationView(View):
    template_name = 'booking_confirmation.html'

    def post(self, request):
        selected_date = request.POST.get('selected_date')
        selected_slot = request.POST.get('selected_slot')
        unique_url = request.POST.get('unique_url')
        user = request.user
        email = user.email

        if 'confirm_booking' in request.POST:
            calendar_event = CalendarEvent.objects.get(unique_url=unique_url)
            attendees = json.loads(calendar_event.attendees) if calendar_event.attendees else []
            attendees.append({
                'name': user.username,
                'email': user.email,
                'selected_date': selected_date,
                'selected_slot': selected_slot,
            })
            calendar_event.attendees = json.dumps(attendees)
            calendar_event.save()

            
            return redirect('home')
        
        context = {
                'selected_date': selected_date,
                'selected_slot': selected_slot,
                'user': user,
                'email': email,
                'unique_url':unique_url,
            }
        return render(request, self.template_name, context)
        
        # Redirect to the home page after Confirm Booking is clicked
        