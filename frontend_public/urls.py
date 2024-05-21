from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(
        "about/",
        TemplateView.as_view(template_name="pages/about.html"),
        name="about",
    ),
    path(
        "changelog/",
        TemplateView.as_view(template_name="pages/changelog.html"),
        name="changelog",
    ),
    path(
        "terms_and_conditions/",
        TemplateView.as_view(template_name="pages/terms_and_conditions.html"),
        name="terms_and_conditions",
    ),
    path(
        "privacy_policy/",
        TemplateView.as_view(template_name="pages/privacy_policy.html"),
        name="privacy_policy",
    ),
]
