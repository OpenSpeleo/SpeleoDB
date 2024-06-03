from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

class _AuthenticatedTemplateView(LoginRequiredMixin, TemplateView):
    # login_url = reverse("account_login")
    login_url = "/login/"


class DashboardView(_AuthenticatedTemplateView):
    template_name = "pages/dashboard.html"


class ProjectView(_AuthenticatedTemplateView):
    template_name = "pages/projects.html"


class AccountView(_AuthenticatedTemplateView):
    template_name = "pages/account.html"
