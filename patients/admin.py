from django.contrib import admin
from .models import PatientProfile

admin.site.register(PatientProfile)

# Connection (social graph between users) is intentionally NOT registered
# in Django admin to preserve relationship privacy.
