from django.http.request import QueryDict
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from speleodb.surveys.api.serializers import ProjectSerializer
from speleodb.surveys.models import Project


class ProjectListApiView(APIView):
    # add permission to check if user is authenticated
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer
    queryset = Project.objects.all()
    lookup_field = "pk"

    # 1. List all
    def get(self, request, *args, **kwargs):
        """
        List all the todo items for given requested user
        """
        projects = Project.objects.filter(owner=request.user.id)
        serializer = ProjectSerializer(projects, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 2. Create
    def post(self, request, *args, **kwargs):
        """
        Create the Todo with given todo data
        """
        data = (
            request.data.dict() if isinstance(request.data, QueryDict) else request.data
        )
        data["owner"] = request.user.id
        serializer = ProjectSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
