from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matchmaking", "0084_investorshortlist"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="is_internal_profile",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Staff-only test/demo/audit profile. Internal profiles remain usable by "
                    "their owner and by explicit Zelda workflows, but are excluded from "
                    "marketplace discovery, matching, public feeds, and Explore."
                ),
            ),
        ),
        migrations.AddField(
            model_name="investorapplication",
            name="is_internal_profile",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Staff-only test/demo/audit profile. Internal profiles remain usable by "
                    "their owner and by explicit Zelda workflows, but are excluded from "
                    "marketplace discovery, matching, public feeds, and Explore."
                ),
            ),
        ),
        migrations.AddField(
            model_name="sellerapplication",
            name="is_internal_profile",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Staff-only test/demo/audit profile. Internal profiles remain usable by "
                    "their owner and by explicit Zelda workflows, but are excluded from "
                    "marketplace discovery, matching, public feeds, and Explore."
                ),
            ),
        ),
        migrations.AddField(
            model_name="buyerapplication",
            name="is_internal_profile",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Staff-only test/demo/audit profile. Internal profiles remain usable by "
                    "their owner and by explicit Zelda workflows, but are excluded from "
                    "marketplace discovery, matching, public feeds, and Explore."
                ),
            ),
        ),
    ]
