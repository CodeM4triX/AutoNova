from django.contrib import admin
from .models import EmailAddress
# Register your models here.
class EmailAddressAdmin(admin.ModelAdmin):
    pass
admin.site.register(EmailAddress, EmailAddressAdmin)