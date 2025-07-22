# -*- coding: utf-8 -*-

from __future__ import annotations

import allauth.account.views as allauth_views
from django.urls import path
from django.urls import re_path
from django.views.generic import TemplateView

from frontend_public.views import LoginView
from frontend_public.views import PasswordResetFromKeyView
from frontend_public.views import PasswordResetView
from frontend_public.views import PeoplePageView
from frontend_public.views import SignUpView

ArianeWebView = TemplateView.as_view(template_name="webviews/ariane.html")

urlpatterns = [
    # Main Pages
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(
        "about/", TemplateView.as_view(template_name="pages/about.html"), name="about"
    ),
    path(
        "people/",
        PeoplePageView.as_view(),
        name="people",
    ),
    path(
        "roadmap/",
        TemplateView.as_view(template_name="pages/roadmap.html"),
        name="roadmap",
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
    # Webviews
    path("webview/ariane/", ArianeWebView, name="webview_ariane"),
    # User Auth Management
    path("login/", LoginView.as_view(), name="account_login"),
    path("logout/", allauth_views.logout, name="account_logout"),
    path("signup/", SignUpView.as_view(), name="account_signup"),
    # path("inactive/", allauth_views.account_inactive, name="account_inactive"),
    re_path(
        r"^account/confirm-email/(?P<key>[-:\w]+)/$",
        allauth_views.confirm_email,
        name="account_confirm_email",
    ),
    # path(
    #     "password/change/",
    #     allauth_views.password_change,
    #     name="account_change_password",
    # ),
    # path("password/set/", allauth_views.password_set, name="account_set_password"),
    # ----- password reset ----- #
    path(
        "account/password/reset/",
        PasswordResetView.as_view(),
        name="account_reset_password",
    ),
    re_path(
        r"^account/password/reset/(?P<uidb36>[0-9A-Za-z@.]+)-(?P<key>[0-9a-z-]+)/$",
        PasswordResetFromKeyView.as_view(),
        name="account_reset_password_from_key",
    ),
    # ================ Unused Confirmation Pages ================ #
    # path(
    #     "confirm-email/",
    #     allauth_views.email_verification_sent,
    #     name="account_email_verification_sent",
    # ),
    # path(
    #     "password/reset/done/",
    #     allauth_views.password_reset_done,
    #     name="account_reset_password_done",
    # ),
    # path(
    #     "password/reset/key/done/",
    #     allauth_views.password_reset_from_key_done,
    #     name="account_reset_password_from_key_done",
    # ),
]
