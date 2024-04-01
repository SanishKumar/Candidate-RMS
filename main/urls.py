from django.urls import include, path
from django import urls
from django.conf import settings
from django.conf.urls.static import static
from .views import *


urlpatterns = [
    path('', home.as_view(), name='home'),
    path('all-jobs/', AllJobs.as_view(), name='all_jobs'),
    path('applied-jobs/', AppliedJobs.as_view(), name='applied_jobs'),
    path('job/<int:pk>/', JobDetail.as_view(), name='job_detail'),
    path('apply-now/<int:job_id>/', ApplyNowView.as_view(), name='apply_now'),
    path('accounts/login/', CustomLoginView.as_view(), name='custom_login'),
    path('accounts/logout/', CustomLogoutView.as_view(), name='custom_logout'),
    path('accounts/register/', RegisterView.as_view(), name='register'),
    path('release_job/', ReleaseJobView.as_view(), name='release_job'),
    path('view_job_applications/', ViewJobApplications.as_view(), name='view_job_applications'),
    path('view-applicants/<slug:job_slug>/', ViewApplicants.as_view(), name='view_applicants'),
    path('view-profile/<slug:applicant_slug>/', ViewProfile.as_view(), name='view_profile'),
    path('view_scheduled_meetings/', ViewScheduledMeetings.as_view(), name='view_scheduled_meetings'),
    path('review_meeting/<slug:applicant_slug>/', ReviewMeetingView.as_view(), name='review_meeting'),
    path('sent-by-mainHr/', SentByMainHr.as_view(), name='sent_by_mainHr'),
    path('get_my_meetings/', GetMyMeetingsView.as_view(), name='get_my_meetings'),
    path('calendar_settings/', CalendarSettingsView.as_view(), name='calendar_settings'),
    path('create_event/', CreateCalendarEventView.as_view(), name='create_calendar_event'),
    path('shared_calendar/<str:unique_url>/', SharedCalendarView.as_view(), name='shared_calendar'),
    path('my-event/', MyEvents.as_view(), name='my_event'),
    path('get_dynamic_meetings/<int:event_id>/', myeventmeetings.as_view(), name='get_event_meetings'),
    path('booking_confirmation/', BookingConfirmationView.as_view(), name='booking_confirmation'),
    


]
