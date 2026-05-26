from django.contrib import admin
from .models import ClientPersonalInfo, ClientStatus, UserLog, Beneficiary, Booking

admin.site.register(ClientPersonalInfo)
admin.site.register(ClientStatus)
admin.site.register(UserLog)
admin.site.register(Beneficiary)
admin.site.register(Booking)
