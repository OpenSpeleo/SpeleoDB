from django.conf import settings
from django.shortcuts import redirect
from django.shortcuts import render
from django.views import View


def redirect_authenticated_user(func):
    def wrapper(obj, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("private:home")

        return func(obj, request, *args, **kwargs)

    return wrapper


class LoginView(View):
    template_name = "auth/login.html"

    @redirect_authenticated_user
    def get(self, request):
        return render(
            request,
            LoginView.template_name,
        )


class PasswordResetFromKeyView(View):
    template_name = "auth/password_reset_from_key.html"

    @redirect_authenticated_user
    def get(self, request, uidb36, key):
        return render(
            request,
            PasswordResetFromKeyView.template_name,
            {
                "uidb36": uidb36,
                "key": key,
            },
        )


class PasswordResetView(View):
    template_name = "auth/password_reset.html"

    @redirect_authenticated_user
    def get(self, request):
        return render(
            request,
            PasswordResetView.template_name,
        )


class SignUpView(View):
    template_names = {
        True: "auth/signup.html",
        False: "auth/signup_closed.html",
    }

    @redirect_authenticated_user
    def get(self, request):
        return render(
            request,
            SignUpView.template_names[settings.DJANGO_ACCOUNT_ALLOW_REGISTRATION],
        )
