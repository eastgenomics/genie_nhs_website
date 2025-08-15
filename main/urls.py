from django.urls import path
from main import views

app_name = 'main'

urlpatterns = [
    path('', views.index, name='index'),
    path('variants/', views.variants, name='variants'),
    path('search/', views.search_view, name='search'),
    path('ajax_variants/', views.ajax_variants, name='ajax_variants'),
]