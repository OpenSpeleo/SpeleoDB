"""Public signed unsubscribe links."""

from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from speleodb.campaigns.views import photo
from speleodb.campaigns.views import test_unsubscribe
from speleodb.campaigns.views import unsubscribe

app_name = "campaigns"
urlpatterns = [
    path("<uuid:campaign_id>/photo/", photo, name="photo"),
    path("unsubscribe/test/", test_unsubscribe, name="test-unsubscribe"),
    # Signed per-account tokens authorize mailbox-provider one-click POSTs.
    path("unsubscribe/<str:token>/", csrf_exempt(unsubscribe), name="unsubscribe"),
]
