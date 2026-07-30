from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ContactoForm
from django.core.mail import send_mail
from django.conf import settings

def contacto(request):

    if request.method == "POST":
        # ContactoForm(request.POST) -> crea formulario usando los datos enviados en la solicitud request.POST
        formulario = ContactoForm(request.POST)

        if formulario.is_valid():

            formulario.save()
            send_mail(
                subject="Nuevo mensaje desde AlphaMarket",
                message=f"""
            Nombre: {formulario.cleaned_data['nombre']}

            Email: {formulario.cleaned_data['email']}

            Mensaje:
            {formulario.cleaned_data['mensaje']}
            """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=["tu_correo@gmail.com"],
            )

            messages.success(request, 'Tu mensaje fue enviado correctamente')
            return redirect("tienda")
        else:
            messages.error(request, 'Existen errores en el formulario')
    else:
        # Se crea un formulario vacio
        formulario = ContactoForm()
        # Pero nunca se usa porque tengo mi propio formulario en html
    return render(request, "tienda/tienda.html")