from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from django.views.generic import RedirectView
from dashboard import views
urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginView.as_view(template_name='login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('login.html', RedirectView.as_view(url='/login/')),
    path('', views.index, name='index'),
    path('api/session', views.session),
    path('api/state/', views.state),
    path('api/import/', views.import_legacy),
    path('api/cartorios/<uuid:registry_uid>/pastas/<uuid:folder_uid>/', views.unlink_folder),
    path('api/items/<str:kind>/', views.items),
    path('api/items/<str:kind>/<uuid:uid>/', views.items),
]
