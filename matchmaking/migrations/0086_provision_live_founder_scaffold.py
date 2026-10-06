from django.db import migrations


def provision_live_founder_scaffold(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Application = apps.get_model('matchmaking', 'Application')
    InvestorApplication = apps.get_model('matchmaking', 'InvestorApplication')
    SellerApplication = apps.get_model('matchmaking', 'SellerApplication')
    BuyerApplication = apps.get_model('matchmaking', 'BuyerApplication')

    try:
        user = User.objects.get(username='jonmason')
    except User.DoesNotExist:
        return

    # Never overwrite a completed role or create a second marketplace role.
    if (
        Application.objects.filter(user_id=user.id).exists()
        or InvestorApplication.objects.filter(user_id=user.id).exists()
        or SellerApplication.objects.filter(user_id=user.id).exists()
        or BuyerApplication.objects.filter(user_id=user.id).exists()
    ):
        return

    founder_name = (f'{user.first_name} {user.last_name}').strip() or user.username
    Application.objects.create(
        user_id=user.id,
        company_name='Interlink Foundry',
        founder_name=founder_name,
        email=user.email or '',
        description='',
        sector='Other',
        stage='Seed',
        is_private=True,
    )


def remove_scaffold(apps, schema_editor):
    Application = apps.get_model('matchmaking', 'Application')
    User = apps.get_model('auth', 'User')
    try:
        user = User.objects.get(username='jonmason')
    except User.DoesNotExist:
        return

    # Reverse only the untouched scaffold this migration created.
    Application.objects.filter(
        user_id=user.id,
        company_name='Interlink Foundry',
        description='',
        sector='Other',
        stage='Seed',
        is_private=True,
        prior_amount_raised=0,
        raising_amount=0,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0085_internal_profile_isolation'),
    ]

    operations = [
        migrations.RunPython(provision_live_founder_scaffold, remove_scaffold),
    ]
