from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("gis", "0045_install_constraint_messages")]
    operations = [migrations.DeleteModel(name="ProjectGeoJSONGeneration")]
