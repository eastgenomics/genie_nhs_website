from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse

from main.lookups import get_variants
from main.utils import CHROMOSOMES


def index(request):
    """Homepage."""
    return render(request, 'main/index.html')


def search_view(request):
    """Main website search that is available on all website pages.

    This view is used to figure out search type and redirect to the
    appropriate page with required parameters. So far the website has 
    only one page that can display search results (variants), but it
    can be used to work with multiple pages.
    """
    # Get search value.
    search_value = request.GET.get('search_value', '')
    
    # Figure out search type and construct redirect url.
    if ':' in search_value and search_value.split(':')[0] in CHROMOSOMES:
        search_key = 'region'
    else:
        search_key = 'gene'
    url = reverse('main:variants') + \
        f'?search_key={search_key}&search_value={search_value}'
    
    # Redirect to the appropriate page.
    return redirect(url)


def ajax_variants(request):
    """Ajax request to obtain data for the variant table."""
    try:
        variants = get_variants(request.GET.get('search_key', ''), 
                                request.GET.get('search_value', ''))
        data = {
            'rows': variants,
            'total': len(variants),
            'error': '',
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'rows': [], 'total': 0, 'error': str(e)}, 
            status=500)        


def variants(request):
    """Variants table page, data is loaded via an ajax request."""
    search_key = request.GET.get('search_key', '')
    search_value = request.GET.get('search_value', '')
    context_dict = {
        'search_value': search_value,
        'variant_data_url': reverse('main:ajax_variants') + \
            f'?search_key={search_key}&search_value={search_value}'
    }
    return render(request, 'main/variants.html', context=context_dict)