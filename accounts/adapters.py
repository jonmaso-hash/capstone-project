import requests
from django.core.files.base import ContentFile

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Pulls the provider's profile photo into UserSettings.profile_picture on
    first signup only — never overwrites a picture the user later uploads or
    changes themselves in Settings. Google's extra_data always includes a
    'picture' URL; Facebook/LinkedIn use different shapes and aren't handled
    here yet.
    """

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

        picture_url = sociallogin.account.extra_data.get('picture')
        if picture_url:
            from usersettings.models import UserSettings

            user_settings = UserSettings.for_user(user)
            if not user_settings.profile_picture:
                try:
                    response = requests.get(picture_url, timeout=5)
                    response.raise_for_status()
                    user_settings.profile_picture.save(
                        f"{user.pk}_{sociallogin.account.provider}.jpg",
                        ContentFile(response.content),
                        save=True,
                    )
                except requests.RequestException:
                    pass

        return user
