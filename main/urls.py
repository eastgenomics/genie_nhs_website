from django.urls import path
from main import views

app_name = 'main'

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('variants/', views.variants, name='variants'),
    path('search/', views.search_view, name='search'),
    path('ajax_variants/', views.ajax_variants, name='ajax_variants'),
    path('ajax_variant_cancer_pcs', views.ajax_variant_cancer_pcs, name='ajax_variant_cancer_pcs'),
]