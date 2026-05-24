from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path('', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    path('dags/<str:dag_id>/', TemplateView.as_view(template_name='dag_detail.html'), name='dag_detail'),
    path('runs/<str:run_id>/', TemplateView.as_view(template_name='run_monitor.html'), name='run_monitor'),
    path('login/', TemplateView.as_view(template_name='login.html'), name='login_page'),
]
