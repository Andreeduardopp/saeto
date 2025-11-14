
import os

from django.forms import ValidationError
from core.models import ModelPadrao
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _


def _get_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    timestamp_str = instance.criado_em.strftime('%Y-%m-%d_%H-%M-%S')
    new_filename = f"{instance.model_type}_{timestamp_str}.{ext}"
    return os.path.join('financial_reports', instance.usuario.username, new_filename)

class FinantialModelsChoices(models.TextChoices):
    BLACK_SCHOLES = 'BLACK_SCHOLES', _('Black-Scholes'),
    BLACK_SCHOLES_MERTON = 'BLACK_SCHOLES_MERTON', _('Black-Scholes-Merton'),
    GENERALIZED_BLACK_SCHOLES_MERTON = 'GENERALIZED_BLACK_SCHOLES_MERTON', _('Generalized Black-Scholes-Merton'),
    COX_ROSS = 'COX_ROSS', _('Cox-Ross Binomial'),
    MONTE_CARLO_EUROPEAN = 'MONTE_CARLO_EUROPEAN', _('Monte-carlo European'),
    MONTE_CARLO_AMERICAN = 'MONTE_CARLO_AMERICAN', _('Monte-carlo American'),

class FinantialModels(ModelPadrao):
    name = models.CharField(max_length=255, default='Financial Model')
    model_type = models.CharField(max_length=100, blank=True, null=True, choices=FinantialModelsChoices.choices)
    parameters = models.JSONField(
        default=dict,
        verbose_name="Simulation Parameters",
        help_text="All input parameters for the simulation"
    )

    results = models.JSONField(
        default=dict,
        verbose_name="Simulation Results",
        help_text="All calculated results from the simulation"
    )

    report = models.FileField(
        upload_to=_get_upload_path,
        null=True,
        blank=True,
        verbose_name="PDF Report",
        validators=[FileExtensionValidator(['pdf'])]
    )

    class Meta:
        abstract = False
        verbose_name = "Financial Simulation"
        verbose_name_plural = "Financial Simulations"
    
    def __str__(self):
        return self.name
    
    def clean(self):
        super().clean()
        if self.pk is None and self.usuario:
            current_count = FinantialModels.objects.filter(usuario=self.usuario).count()
            if current_count >= 41:
                raise ValidationError(
                    _('You have reached the maximum limit of 40 financial models.'),
                    code='limit_exceeded',
                    params={'max_models': 40},
                )

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.name or self.name == 'Financial Model':
            criado_em = timezone.now().strftime('%d/%m/%Y %H:%M')
            if self.criado_em:
                criado_em = self.criado_em.strftime('%d/%m/%Y %H:%M')
            self.name = f"{self.get_model_type_display()} - {criado_em}"
        if self.pk is None:
            self.full_clean()
        super().save(*args, **kwargs)