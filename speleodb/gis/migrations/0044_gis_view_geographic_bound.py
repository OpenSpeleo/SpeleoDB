from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [("gis", "0043_geometry_metadata_landmark_icon")]

    operations = [
        migrations.AddField(
            model_name="gisview",
            name="geographic_bound",
            field=models.ForeignKey(
                blank=True,
                default=None,
                help_text=(
                    "Optional Polygon restricting the public web viewer display only. "
                    "Raw GeoJSON downloads and OGC access remain unrestricted."
                ),
                null=True,
                on_delete=models.PROTECT,
                related_name="bounded_gis_views",
                to="gis.gisgeometry",
            ),
        ),
    ]
