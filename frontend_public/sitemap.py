from django.contrib import sitemaps
from django.urls import reverse


class HomeViewSitemap(sitemaps.Sitemap):  # type: ignore[type-arg]
    priority = 1.0
    changefreq = "daily"

    def items(self) -> list[str]:
        return ["home"]

    def location(self, item: str) -> str:
        return reverse(item)


class PublicViewSitemap(sitemaps.Sitemap):  # type: ignore[type-arg]
    priority = 0.8
    changefreq = "daily"

    def items(self) -> list[str]:
        return [
            "about",
            "people",
            "roadmap",
            "changelog",
            "terms_and_conditions",
            "privacy_policy",
        ]

    def location(self, item: str) -> str:
        return reverse(item)
