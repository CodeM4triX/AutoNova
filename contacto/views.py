from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ContactoForm
from django.core.mail import send_mail
from django.conf import settings
from propietario.models import PropietarioInfo
from django.core.mail import EmailMessage

def contacto(request):

    if request.method == "POST":
        # ContactoForm(request.POST) -> crea formulario usando los datos enviados en la solicitud request.POST
        formulario = ContactoForm(request.POST)

        if formulario.is_valid():
            formulario.save()
            # RECUPERAR EL EMAIL DEL PROPIETARIO DESDE LA BASE DE DATOS
            propietario = PropietarioInfo.objects.first()

            # Correo de respaldo por si aún no creas el objeto en el admin
            email_destino = (
                propietario.email if propietario else "tu_correo@gmail.com"
            )
            
            # Creamos el objeto de correo estructurado
            correo = EmailMessage(
                subject="Nuevo mensaje desde AlphaMarket",
                body=f"""
                    Nombre: {formulario.cleaned_data['nombre']}
                    Email: {formulario.cleaned_data['email']}
                    
                    Mensaje:
                    {formulario.cleaned_data['mensaje']}
                """,
                from_email=settings.DEFAULT_FROM_EMAIL, # Tu correo de servidor (del settings)
                to=[email_destino],                      # El correo del dueño
                reply_to=[formulario.cleaned_data['email']] # <-- ¡AQUÍ COLOCAS EL CORREO DEL CLIENTE!
            )
            
            # Se envía el correo
            correo.send()

            messages.success(request, 'Tu mensaje fue enviado correctamente')
            return redirect("tienda")
        else:
            messages.error(request, 'Existen errores en el formulario')
    else:
        # Se crea un formulario vacio
        formulario = ContactoForm()
        # Pero nunca se usa porque tengo mi propio formulario en html
    return render(request, "tienda/tienda.html")