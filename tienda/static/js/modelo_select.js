document.addEventListener('DOMContentLoaded', function() {
    const marcaSelect = document.getElementById('id_marca');
    const modeloSelect = document.getElementById('id_modelo');
  
    marcaSelect.addEventListener('change', function() {
      const selectedMarcaId = this.value;
      console.log(selectedMarcaId)

      if (!isNaN(selectedMarcaId)) { //is Not an Number -> No es un numero_______________ !isNaN  -> es un numero
  
        const url = `/get_modelos/?marca_id=${selectedMarcaId}`;
        
        fetch(url)
          .then(response => response.json())
          .then(data => {
            console.log(data);
            modeloSelect.innerHTML = ''; // Elimina las opciones existentes
    
            // Agregar una opción vacía como la primera opción
            const emptyOption = document.createElement('option');
            emptyOption.value = ''; // Valor vacío
            emptyOption.text = ''; // Texto vacío
            modeloSelect.appendChild(emptyOption);

            data.forEach(modelo => {
              const option = document.createElement('option');
              option.value = modelo.id;
              let texto = modelo.nombre;

              if (modelo.generacion) {
                  texto += ` ${modelo.generacion}`;
              }
              if (modelo.chasis) {
                  texto += ` (${modelo.chasis})`;
              }
              if (modelo.anios_produccion) {
                  texto += ` (${modelo.anios_produccion})`;
              }
              option.text = texto;
              modeloSelect.appendChild(option);
            });
          })
          .catch(error => console.error('Error:', error));
      }else {
        console.log('else');
        modeloSelect.innerHTML = ''; // Elimina las opciones existentes
      }
    }); 
  });