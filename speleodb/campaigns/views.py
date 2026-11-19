"""Public campaign pages and authenticated invitation preferences."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignDismissal
from speleodb.users.models import User

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpRequest
    from rest_framework.request import Request


class DonationCampaignDismissalView(APIView):
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
        DonationCampaignDismissal.objects.update_or_create(
            campaign=campaign,
            user=request.user,
            defaults={"modified_date": timezone.now()},
        )
        return Response(status=204)


@require_GET
def thank_you(request: HttpRequest) -> TemplateResponse:
    return TemplateResponse(request, "pages/campaign_thank_you.html")
