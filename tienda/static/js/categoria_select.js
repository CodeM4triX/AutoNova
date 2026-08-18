document.addEventListener('DOMContentLoaded', function() {

  const sistemaSelect = document.getElementById('id_sistema');
  const categoriaSelect = document.getElementById('id_categoria');
  const productoMarcaSelect = document.getElementById('id_producto_marca');

  sistemaSelect.addEventListener('change', function() {
    const selectedSistemaId = this.value;
    console.log(selectedSistemaId);
    
    const url = `/get_categorias/?sistema_id=${selectedSistemaId}`;
    console.log(url);
    fetch(url)
      .then(response => response.json())
      .then(data => {
        //console.log(data);
        categoriaSelect.innerHTML = ''; // Elimina las opciones existentes

        // Agregar una opción vacía como la primera opción
        const emptyOption = document.createElement('option');
        emptyOption.value = ''; // Valor vacío
        emptyOption.text = ''; // Texto vacío
        categoriaSelect.appendChild(emptyOption);
            
        data.forEach(categoria => {
          //console.log(modelo);
          const option = document.createElement('option');
          option.value = categoria.id;
          option.text = categoria.nombre;
          categoriaSelect.appendChild(option);
        });
      })
      .catch(error => console.error('Error:', error));
  });

  sistemaSelect.addEventListener('change', function() {
    const selectedSistemaId = this.value;
    console.log('Estoy en change categoriaSelect');

    const url1 = `/get_productoMarca/?sistema_id=${selectedSistemaId}`;
    console.log(url1);
    fetch(url1)
      .then(response => response.json())
      .then(data => {
        //console.log(data);
        productoMarcaSelect.innerHTML = ''; // Elimina las opciones existentes

        // Agregar una opción vacía como la primera opción
        const emptyOption = document.createElement('option');
        emptyOption.value = ''; // Valor vacío
        emptyOption.text = ''; // Texto vacío
        productoMarcaSelect.appendChild(emptyOption);
        
        data.forEach(marcaProducto => {
          //console.log(modelo);
          const option = document.createElement('option');
          option.value = marcaProducto.id;
          option.text = marcaProducto.nombre;
          productoMarcaSelect.appendChild(option);
        });
      })
      .catch(error => console.error('Error:', error));
  }); 
})
