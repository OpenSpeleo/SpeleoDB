"""Authenticated campaign invitation preferences."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core import signing
from django.http import FileResponse
from django.http import Http404
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from speleodb.campaigns.mail import UNSUBSCRIBE_SALT
from speleodb.campaigns.models import CampaignDismissal
from speleodb.campaigns.models import DonationCampaign
from speleodb.users.models import User

if TYPE_CHECKING:
    from uuid import UUID

    from rest_framework.request import Request


class CampaignDismissalView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="v2_user_donation_campaigns_dismiss_create",
        request=None,
        responses={204: None},
    )
    def post(self, request: Request, campaign_id: UUID) -> Response:
        if not isinstance(request.user, User):
            raise NotAuthenticated
        campaign = get_object_or_404(DonationCampaign, pk=campaign_id)
        CampaignDismissal.objects.update_or_create(
            campaign=campaign,
            user=request.user,
            defaults={"modified_date": timezone.now()},
        )
        return Response(status=204)


def unsubscribe(request: HttpRequest, token: str) -> HttpResponse:
    if request.method not in {"GET", "POST"}:
        return HttpResponseNotAllowed(["GET", "POST"])
    try:
        data = signing.loads(token, salt=UNSUBSCRIBE_SALT)
        user = get_object_or_404(User, pk=data["user_id"], email=data["email"])
    except (signing.BadSignature, KeyError, ValueError, TypeError) as error:
        raise Http404("Invalid unsubscribe link.") from error
    if request.method == "POST":
        User.objects.filter(pk=user.pk).update(email_on_speleodb_updates=False)
        return HttpResponse(
            "You are unsubscribed from SpeleoDB updates. "
            "Your other account settings are unchanged.",
            content_type="text/plain",
        )
    return TemplateResponse(request, "admin/campaigns/unsubscribe.html")


@require_GET
def test_unsubscribe(request: HttpRequest) -> HttpResponse:
    return HttpResponse(
        "This is a test email. No subscription has been changed.",
        content_type="text/plain",
    )


@require_GET
def photo(request: HttpRequest, campaign_id: UUID) -> FileResponse:
    campaign = get_object_or_404(DonationCampaign, pk=campaign_id)
    if not campaign.photo:
        raise Http404
    response = FileResponse(campaign.photo.open("rb"))
    response["Cache-Control"] = "public, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response
