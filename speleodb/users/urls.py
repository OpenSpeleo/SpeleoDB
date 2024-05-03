from django.urls import path

from speleodb.users.views import user_detail_view
from speleodb.users.views import user_redirect_view
from speleodb.users.views import user_update_view

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("<str:pk>/", view=user_detail_view, name="detail"),
]
