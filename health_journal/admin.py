from django.contrib import admin

# Health entries, medications and vital signs are PRIVATE patient data.
# They are intentionally NOT registered in Django admin to preserve confidentiality.
# Use the admin panel (/admin-panel/) for aggregated statistics only.
