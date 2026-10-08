# Staff two-factor authentication

Staff access requires a password/social sign-in and a verified authenticator
or one-use recovery code. Existing sessions must complete enrollment or the
challenge before using staff privileges. Regular member accounts are unchanged.

On first staff sign-in, add the displayed setup key to a compatible time-based
authenticator app. Confirm the current password if the account has one, then
enter the app's six-digit code. Save the ten recovery codes securely; they are
shown once. Staff MFA pages contain no third-party scripts or analytics.

The factor proof lasts at most eight hours and is lost at logout. Returning
from impersonation requires a new challenge because switching users flushes
the session. Staff-owned API bearer tokens are rejected: use an MFA-verified
session for staff API access and a separate non-staff account for enterprise
integrations.

TOTP secrets are Fernet-encrypted using a domain-separated key derived from
the deployment SECRET_KEY. Preserve that key across deploys. When rotating it,
configure Django SECRET_KEY_FALLBACKS with the old key until encrypted records
have been migrated; do not put secrets in source control. Recovery codes are
stored as SHA-256 hashes of 128-bit random values. TOTP counters and recovery
code consumption are serialized using the account's database row lock.

If both the authenticator and all recovery codes are lost, an operator with
trusted server-shell access must independently verify the account owner.
Then run:

```sh
python manage.py reset_staff_mfa USERNAME --confirm-username USERNAME
```

This resets enrollment and logs the user ID. It does not grant staff access;
old MFA proofs stop working and the account must enroll again. No web or email
endpoint disables MFA.
