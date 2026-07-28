from django.contrib import admin
from pedido.models import Pedido, LineaPedido, RankingPedido

# Register your models here.
class PedidoAdmin(admin.ModelAdmin):
    pass
class RankingAdmin(admin.ModelAdmin):
    list_display = ("nombre","ranking")
    readonly_fields = ("nombre", "ranking")

admin.site.register(Pedido)
admin.site.register(LineaPedido)
admin.site.register(RankingPedido, RankingAdmin)