from django.db import models

# Create your models here.
class PropietarioInfo(models.Model):
    pais = models.CharField(max_length=20)
    ciudad = models.CharField(max_length=20)
    barrio = models.CharField(max_length= 20, blank=True)
    avenida = models.CharField(max_length=20, blank=True)
    nro_inmueble = models.CharField(max_length=10, blank=True)
    email = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "Informacion del Propietario"
        verbose_name_plural = "Informacion del Propietario"

    def save(self, *args, **kwargs):
        # Si ya existe un registro y se intenta crear uno nuevo (sin ID), lo bloquea
        if not self.pk and PropietarioInfo.objects.exists():
            raise ValidationError("Solo se permite un registro de configuración de propietario.")
        return super().save(*args, **kwargs)

    