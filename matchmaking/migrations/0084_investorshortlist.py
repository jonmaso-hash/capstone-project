from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("matchmaking", "0083_application_revenue_period"),
    ]

    operations = [
        migrations.CreateModel(
            name="InvestorShortlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("saved_at", models.DateTimeField(auto_now_add=True)),
                ("note", models.TextField(blank=True)),
                ("application", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shortlisted_by", to="matchmaking.application")),
                ("investor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shortlist_entries", to="matchmaking.investorapplication")),
            ],
            options={"ordering": ["-saved_at"]},
        ),
        migrations.AddConstraint(
            model_name="investorshortlist",
            constraint=models.UniqueConstraint(fields=("investor", "application"), name="unique_investor_shortlist_entry"),
        ),
    ]
