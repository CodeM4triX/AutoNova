
document.addEventListener("DOMContentLoaded", function () {

    const modal = document.getElementById("modal-imagen");
    const imagenAmpliada = document.getElementById("imagen-ampliada");

    const btnAnterior = document.getElementById("anterior");
    const btnSiguiente = document.getElementById("siguiente");
    const btnCerrar = document.querySelector(".cerrar-modal");

    console.log(btnAnterior);
    console.log(btnSiguiente);
    console.log(btnCerrar);
    console.log(modal);

    let imagenesActuales = [];
    let indiceActual = 0;

    // Recorre todas las galerías de la página
    document.querySelectorAll(".box_img").forEach(function (galeria) {

        const imagenPrincipal = galeria.querySelector(".imagen-principal");
        const miniaturas = galeria.querySelectorAll(".miniatura");
        
        // Si el producto no tiene imágenes, lo ignoramos
        if (!imagenPrincipal || miniaturas.length === 0) {
            return;
        }
        // Cambiar imagen principal
        miniaturas.forEach(function (miniatura, indice) {

            miniatura.addEventListener("click", function () {

                imagenPrincipal.src = this.src;
                indiceActual = indice;

            });

        });

        // Abrir modal
        imagenPrincipal.addEventListener("click", function () {
            console.log("CLICK EN IMAGEN PRINCIPAL");
            console.log("Abriendo modal");
            console.log(imagenesActuales.length);
            console.log(indiceActual);

            imagenesActuales = Array.from(miniaturas);

            // Buscar qué imagen está visible
            indiceActual = imagenesActuales.findIndex(function(img){

                return img.src === imagenPrincipal.src;

            });

            if(indiceActual === -1){
                indiceActual = 0;
            }

            imagenAmpliada.src = imagenPrincipal.src;

            modal.style.display = "flex";

        });

    });

    // Imagen siguiente
    btnSiguiente.addEventListener("click", function (e) {
        console.log("Siguiente");
        e.stopPropagation();

        indiceActual++;

        if (indiceActual >= imagenesActuales.length) {
            indiceActual = 0;
        }

        imagenAmpliada.src = imagenesActuales[indiceActual].src;

    });

    // Imagen anterior
    btnAnterior.addEventListener("click", function (e) {
        console.log("Anterior");
        e.stopPropagation();

        indiceActual--;

        if (indiceActual < 0) {
            indiceActual = imagenesActuales.length - 1;
        }

        imagenAmpliada.src = imagenesActuales[indiceActual].src;

    });

    // Cerrar con la X
    btnCerrar.addEventListener("click", function () {

        modal.style.display = "none";

    });

    // Cerrar haciendo clic fuera de la imagen
    modal.addEventListener("click", function (e) {

        if (e.target === modal) {

            modal.style.display = "none";

        }

    });

});