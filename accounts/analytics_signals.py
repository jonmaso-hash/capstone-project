from allauth.account.signals import user_signed_up
from django.dispatch import receiver


@receiver(user_signed_up)
def track_social_signup(sender, request, user, **kwargs):
    from matchmaking.product_analytics import track
    track('signup_completed', user.pk, f'user:{user.pk}', occurred_at=user.date_joined, method='allauth')
