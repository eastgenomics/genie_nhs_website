from django.conf import settings

def project_settings(request):
    """Provides selected Django project settings to all templates."""
    return {
        'GENIE_VERSION': settings.GENIE_VERSION,
        'GOOGLE_ANALYTICS_ID': settings.GOOGLE_ANALYTICS_ID,
    }