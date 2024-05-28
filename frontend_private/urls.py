from django.urls import path
from django.views.generic import TemplateView

app_name = "private"
urlpatterns = [
    path(
        "",
        TemplateView.as_view(template_name="pages/dashboard.html"),
        name="home",
    ),
    path(
        "projects/",
        TemplateView.as_view(template_name="pages/projects.html"),
        name="projects",
    ),
    path(
        "account/",
        TemplateView.as_view(template_name="pages/account.html"),
        name="account",
    ),
]
