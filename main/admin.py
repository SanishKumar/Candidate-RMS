from django.contrib import admin
from .models import *
# admin.py



# Register your models here
if admin.site.is_registered(Profile):
    admin.site.unregister(Profile)
    
class UserProfileAdmin(admin.ModelAdmin):
    # Customize the display in the admin panel if needed
    list_display = ['user', 'is_hr', 'is_teamlead', 'is_manager', 'is_mainHr', 'is_teamMember']

admin.site.register(Profile, UserProfileAdmin)
admin.site.register(Job)
admin.site.register(JobApplication)
admin.site.register(MeetingSchedule)
admin.site.register(RejectionDetails)
admin.site.register(AcceptanceDetails)
admin.site.register(MeetingReview)
admin.site.register(ManagerMainHrDecision)
admin.site.register(EmailLog)
admin.site.register(UserCalendarSettings)
admin.site.register(CalendarEvent)