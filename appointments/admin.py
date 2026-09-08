from django.contrib import admin
from .models import Appointment, Doctor, AvailabilitySlot

admin.site.register(Appointment)
admin.site.register(Doctor)
admin.site.register(AvailabilitySlot)
