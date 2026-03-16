#apps/blockchain/models.py
# apps/blockchain/models.py

from django.db import models


class BlockchainTransaction(models.Model):
    """
    Audit log of all blockchain transactions.
    Useful for debugging, admin panel, and audit trail.
    """

    TRANSACTION_TYPES = [
        ('create', 'Prescription Created'),
        ('fill', 'Prescription Filled'),
        ('cancel', 'Prescription Cancelled'),
        ('verify', 'Prescription Verified'),
    ]

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]

    prescription_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Prescription ID this transaction relates to"
    )
    transaction_hash = models.CharField(
        max_length=66,
        unique=True,
        null=True,
        blank=True,
        help_text="Ethereum transaction hash (0x...)"
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    block_number = models.IntegerField(null=True, blank=True)
    gas_used = models.IntegerField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Django user who triggered this transaction"
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error details if transaction failed"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.transaction_type} - "
            f"{self.prescription_id} - "
            f"{self.status}"
        )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Blockchain Transaction'
        verbose_name_plural = 'Blockchain Transactions'
        indexes = [
            models.Index(fields=['prescription_id']),
            models.Index(fields=['transaction_hash']),
            models.Index(fields=['status']),
        ]