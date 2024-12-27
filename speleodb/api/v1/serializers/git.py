import datetime

from django.core.exceptions import ValidationError
from rest_framework import serializers

from speleodb.git_engine.core import GitCommit
from speleodb.surveys.models import Project


class CommitSerializer(serializers.Serializer):
    """
    Serializer for Git Commit objects.
    """

    commit_hash = serializers.CharField(source="hexsha")
    commit_hash_short = serializers.SerializerMethodField()
    author_name = serializers.CharField(source="author.name")
    author_email = serializers.CharField(source="author.email")
    authored_date = serializers.DateTimeField(
        source="authored_datetime", format="%Y/%m/%d %H:%M"
    )
    committer_name = serializers.CharField(source="committer.name")
    committer_email = serializers.CharField(source="committer.email")
    committed_date = serializers.DateTimeField(
        source="committed_datetime", format="%Y/%m/%d %H:%M"
    )
    message = serializers.CharField(read_only=True)
    parents = serializers.ListField(child=serializers.CharField())

    formats = serializers.SerializerMethodField()

    def create(self, validated_data):
        raise serializers.ValidationError("This serializer is read-only.")

    def update(self, instance, validated_data):
        raise serializers.ValidationError("This serializer is read-only.")

    def get_commit_hash_short(self, obj: GitCommit) -> str:
        """
        Returns the short version of the commit hash (7 characters by GitHub standard).
        """
        return obj.hexsha_short

    def get_formats(self, obj: GitCommit) -> list[str]:
        """
        Returns the short version of the commit hash (7 characters by GitHub standard).
        """
        project = self.context.get("project")
        if project is not None:
            if not isinstance(project, Project):
                raise ValidationError(
                    f"Received unknown type for `project`: `{type(project)}`, "
                    "expected `Project`"
                )

            # Matching the TZ of Git Commit which are on UTC
            commit_date = datetime.datetime.fromtimestamp(
                obj.authored_date, tz=datetime.UTC
            )

            return [
                dl_format.format.lower()
                for dl_format in project.formats_downloadable
                if dl_format.creation_date.replace(microsecond=0) <= commit_date
            ]

        return []

    def to_representation(self, instance: GitCommit):
        """
        Custom representation logic for the commit object.
        - Includes the list of parent commit hashes.
        - Formats the authored and committed date-time fields.
        """
        representation = super().to_representation(instance)
        # Add additional fields or formatting if necessary.
        representation["parents"] = [parent.hexsha for parent in instance.parents]
        return representation


class CommitListSerializer(serializers.ListSerializer):
    """
    Serializer for a list of Git Commit objects.
    """

    child = CommitSerializer()

    def to_representation(self, data):
        """
        Customize the list serialization.
        """
        # Sort commits by date (descending) if needed
        data = sorted(data, key=lambda commit: commit.authored_datetime, reverse=True)
        return super().to_representation(data)
