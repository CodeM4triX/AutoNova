from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.conf import settings


def paginar_productos(request, queryset):
    por_pagina = getattr(settings, 'TIENDA_PRODUCTOS_POR_PAGINA', 10)
    paginator = Paginator(queryset, por_pagina)
    page_number = request.GET.get('page', 1)

    try:
        return paginator.page(page_number)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)