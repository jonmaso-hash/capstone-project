from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0016_professional_profiles")]
    operations = [migrations.AddField(model_name="personprofile", name="is_public", field=models.BooleanField(default=False, help_text="Publish my professional overview publicly."))]
