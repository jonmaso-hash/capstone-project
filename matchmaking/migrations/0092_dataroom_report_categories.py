from django.db import migrations, models


CATEGORIES = [
    ('PITCH_DECK', 'Pitch Deck'), ('BUSINESS_PLAN', 'Business Plan'),
    ('MEMO', 'Memo'), ('ZELDA_REPORT', 'Zelda Report'),
    ('CAP_TABLE', 'Cap Table'), ('FINANCIALS', 'Financials'),
    ('CUSTOMER_METRICS', 'Customer Metrics'), ('REVENUE_BREAKDOWN', 'Revenue Breakdown'),
    ('CONTRACTS', 'Contracts'), ('LEGAL_IP', 'Legal / IP'),
    ('PRODUCT_ROADMAP', 'Product Roadmap'), ('TEAM_INFO', 'Team Information'),
    ('OTHER', 'Other'),
]


class Migration(migrations.Migration):
    dependencies = [('matchmaking', '0091_hash_business_email_codes')]
    operations = [
        migrations.AlterField(model_name='dataroomdocument', name='category',
                              field=models.CharField(choices=CATEGORIES, default='OTHER', max_length=20)),
        migrations.AlterField(model_name='dataroominformationrequest', name='category',
                              field=models.CharField(choices=CATEGORIES, max_length=20)),
    ]
