#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from speleodb.surveys.api.serializers import ProjectSerializer
from speleodb.surveys.api.utils import SortedResponse
from speleodb.surveys.models import Permission
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
        usr_projects = [
            (perm.project, perm.level_name)
            for perm in request.user.rel_permissions.all()
        ]

        usr_projects = sorted(
            usr_projects, key=lambda proj: proj[0].modified_date, reverse=True
        )

        projects, levels = zip(*usr_projects, strict=False)
        serializer = ProjectSerializer(projects, many=True)

        results = []
        for proj_dict, level in zip(serializer.data, levels, strict=False):
            proj_dict["permission"] = level
            results.append(proj_dict)

        return SortedResponse(results, status=status.HTTP_200_OK)

    # 2. Create
    @csrf_exempt
    def post(self, request, *args, **kwargs):
        """
        Create the Todo with given todo data
        """
        serializer = ProjectSerializer(data=request.data)
        if serializer.is_valid():
            proj = serializer.save()
            Permission.objects.create(
                project=proj, user=request.user, level=Permission.Level.OWNER
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
