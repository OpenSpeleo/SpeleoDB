from django.contrib import sitemaps
from django.urls import reverse


class HomeSitemap(sitemaps.Sitemap):  # type: ignore[type-arg]
    priority = 1.0
    changefreq = "daily"

    def items(self) -> list[str]:
        return ["home"]

    def location(self, item: str) -> str:
        return reverse(item)


class AboutSitemap(sitemaps.Sitemap):  # type: ignore[type-arg]
    priority = 0.8
    changefreq = "daily"

    def items(self) -> list[str]:
        return [
            "about",
            "people",
            "roadmap",
            "changelog",
        ]

    def location(self, item: str) -> str:
        return reverse(item)


class LegalSitemap(sitemaps.Sitemap):  # type: ignore[type-arg]
    priority = 0.3
    changefreq = "daily"

    def items(self) -> list[str]:
        return [
            "terms_and_conditions",
            "privacy_policy",
        ]

    def location(self, item: str) -> str:
        return reverse(item)
