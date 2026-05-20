# banking_api/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class LedgerAccount(models.Model):
    ACCOUNT_TYPES = [
        ('checking', 'Checking'),
        ('savings', 'Savings'),
        ('escrow', 'Escrow Operational'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='banking_accounts')
    account_number = models.CharField(max_length=32, unique=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='checking')
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ledger Account"
        verbose_name_plural = "Ledger Accounts"

    def __str__(self):
        return f"{self.user.username} - {self.account_type.upper()} (*{self.account_number[-4:]})"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Internal Transfer'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    account = models.ForeignKey(LedgerAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    reference_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    description = models.CharField(max_length=255, blank=True, null=True)
    execution_timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transaction Record"
        verbose_name_plural = "Transaction Records"
        ordering = ['-execution_timestamp']

    def __str__(self):
        return f"{self.transaction_type.upper()} - {self.amount} ({self.status})"