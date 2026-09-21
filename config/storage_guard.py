"""
Production must not silently store uploads on a disposable disk.

Found on the first Render deploy: no S3 bucket was configured, so every
FileField wrote to the container's own filesystem. Uploads worked. The success
message was accurate at the moment it was shown. The files were then destroyed
by the next deploy, with no error anywhere, because a container's disk is not
storage -- it is scratch space that happens to accept writes.

That is the worst shape a data-loss bug can take: the user is told it worked,
nothing logs a problem, and the loss surfaces later with no way to tell what
was lost. A founder's cap table can disappear this way.

This makes the combination deliberate rather than accidental. It lives outside
any Django app because it runs while settings are still being built.

Deliberately not absolute. Bringing up a new environment legitimately happens
before object storage exists -- proving the database connects, running the
first migrations, checking that the service boots at all -- and a guard that
made that impossible would just be switched off permanently. So an explicit
ALLOW_EPHEMERAL_MEDIA says "yes, I know uploads are disposable here". What the
guard forbids is arriving in that state by omission.

The asymmetry is the point: turning it on is a decision someone makes and can
be asked about. Leaving a bucket unset is not.
"""
from django.core.exceptions import ImproperlyConfigured


def refuse_ephemeral_media_in_production(debug, bucket_name, acknowledged):
    """Raise ImproperlyConfigured when production has nowhere durable to write."""
    if debug or bucket_name or acknowledged:
        return
    raise ImproperlyConfigured(
        'Refusing to start: DEBUG is False and AWS_STORAGE_BUCKET_NAME is not set, '
        'so uploaded files would be written to this container\'s local disk and '
        'destroyed on the next deploy. Users would be told their upload succeeded. '
        'Set AWS_STORAGE_BUCKET_NAME (with AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY '
        'and AWS_S3_REGION_NAME) to store uploads durably. If this environment is '
        'deliberately disposable -- a first deploy, a smoke test, an environment '
        'that will never accept a real upload -- set ALLOW_EPHEMERAL_MEDIA=1 to '
        'acknowledge that uploaded files will be lost.'
    )
