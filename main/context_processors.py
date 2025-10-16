from django.conf import settings

def genie_version(request):
    return {
        'GENIE_VERSION': settings.GENIE_VERSION,
    }