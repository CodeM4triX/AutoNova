from decimal import Decimal

from tienda.models import Producto

class Carro:
    def __init__(self, request):
        self.request = request
        self.session = request.session
        carro = self.session.get('carro')
        if not carro:
            carro = self.session['carro'] = {}
        self.carro = carro

    def agregar(self, producto):
        self.request.session['ultima_categoria'] = producto.categoria.id
        
        # cuando el producto no tiene imagen, se asigna una imagen por defecto
        #imagen = producto.imagen.url if producto.imagen else '/static/img/default.png'
        primera_imagen = producto.imagenes.first()

        if primera_imagen:
            imagen = primera_imagen.imagen.url
        else:
            imagen = '/static/img/default.png'
            
        precio_unitario = Decimal(str(producto.precio))

        if str(producto.id) not in self.carro.keys():
            self.carro[str(producto.id)] = {
                'producto_id': producto.id,
                'nombre': producto.nombre,
                'costo': str(precio_unitario),
                'precio': str(precio_unitario),
                'cantidad': 1,
                'imagen': imagen,
            }
        else:
            for key, value in self.carro.items():
                if key == str(producto.id):
                    value['cantidad'] = value['cantidad'] + 1
                    total_linea = Decimal(value['precio']) + precio_unitario
                    value['precio'] = str(total_linea)
                    break
        self.guardar_carro()

    def guardar_carro(self):
        self.session['carro'] = self.carro
        self.session.modified = True

    def eliminar(self, producto):
        producto.id = str(producto.id)
        if producto.id in self.carro:
            del self.carro[producto.id]
            self.guardar_carro()

    def restar_producto(self, producto):
        precio_unitario = Decimal(str(producto.precio))
        for key, value in self.carro.items():
            if key == str(producto.id):
                value['cantidad'] = value['cantidad'] - 1
                total_linea = Decimal(value['precio']) - precio_unitario
                value['precio'] = str(total_linea)
                if value['cantidad'] == 0:
                    self.eliminar(producto)
                break
        self.guardar_carro()

    def limpiar_carro(self):
        self.session['carro'] = {}
        self.session.modified = True