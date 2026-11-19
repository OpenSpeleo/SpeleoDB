"""Public campaign pages."""

from django.urls import path

from speleodb.campaigns.views import thank_you

app_name = "campaigns"
urlpatterns = [
    path("thank-you/", thank_you, name="thank-you"),
]
