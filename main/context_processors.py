from django.conf import settings

def project_settings(request):
    return {
        'GENIE_VERSION': settings.GENIE_VERSION,
        'GOOGLE_ANALYTICS_ID': settings.GOOGLE_ANALYTICS_ID,
    }