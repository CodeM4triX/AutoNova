$(document).ready(function() {
  const marcaSelect = document.getElementById('id_marca');
  const modeloSelect = document.getElementById('id_modelo');
  document.getElementById('search_button').addEventListener('click', mensajes_error, false);

  function mensajes_error(e){
    e.preventDefault(); // Evitar que el formulario se envíe
      
    const selectedMarcaId = marcaSelect.value;
    const selectedModeloId = modeloSelect.value;

    // Check if marca is selected
    if (selectedMarcaId == 'Elige una marca' || selectedMarcaId == '') {
      $(marcaSelect).addClass('addclass');
      // Remover la clase después de 1 segundos
      setTimeout(function() {
        $(marcaSelect).removeClass('addclass');
      }, 1000);
    }
  
    // Check if modelo is selected
    if (selectedModeloId == 'Elige un modelo' || selectedModeloId == '') {
      $(modeloSelect).css({'color':'red','border':'1px solid red','font-weight':'bold'});
      // Eliminar el estilo después de 1 segundos
      setTimeout(function() {
        $(modeloSelect).css({'color':'', 'border':'','font-weight':''});
      }, 1000);
    }
    // Check if both marca and modelo are selected
    if (selectedMarcaId != 'Elige una marca' && selectedMarcaId != '' && selectedModeloId != 'Elige un modelo' && selectedModeloId != '') {
      // Redirect to another page with selected brand and model as parameters
      window.location.href = `/filter_products/?marca_id=${selectedMarcaId}&modelo_id=${selectedModeloId}`;
    }
  }
});
  
  