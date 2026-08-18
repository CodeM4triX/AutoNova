document.addEventListener("DOMContentLoaded", function () {

    const categoriaSelect = document.getElementById("id_categoria");

    if (!categoriaSelect) return;

    let detalles = [];

    function obtenerDetallesSeleccionados() {

        const usados = [];

        document.querySelectorAll("select[id$='-detalle']").forEach(select => {
            if (select.value) {
                usados.push(select.value);
            }
        });

        return usados;
    }

    function actualizarSelects() {

        const usados = obtenerDetallesSeleccionados();

        document.querySelectorAll("select[id$='-detalle']").forEach(select => {

            const valorActual = select.value;

            select.innerHTML = "";

            const opcionVacia = document.createElement("option");
            opcionVacia.value = "";
            opcionVacia.textContent = "---------";
            select.appendChild(opcionVacia);

            detalles.forEach(detalle => {

                // Si ya está usado por otro select, no lo mostramos
                if (
                    usados.includes(String(detalle.id)) &&
                    String(detalle.id) !== valorActual
                ) {
                    return;
                }

                const option = document.createElement("option");

                option.value = detalle.id;
                option.textContent = detalle.nombre;

                if (String(detalle.id) === valorActual) {
                    option.selected = true;
                }

                select.appendChild(option);

            });

        });

    }

    function cargarDetalles() {

        const categoriaId = categoriaSelect.value;

        if (!categoriaId) {
            detalles = [];
            actualizarSelects();
            return;
        }

        fetch(`/get_detalles/?categoria_id=${categoriaId}`)
            .then(response => response.json())
            .then(data => {

                detalles = data;

                actualizarSelects();

            })
            .catch(error => {
                console.error("Error al cargar detalles:", error);
            });

    }

    categoriaSelect.addEventListener("change", cargarDetalles);

    document.addEventListener("change", function (e) {

        if (e.target.matches("select[id$='-detalle']")) {
            actualizarSelects();
        }

    });

    document.addEventListener("formset:added", function () {

        setTimeout(() => {
            actualizarSelects();
        }, 0);

    });

    document.addEventListener("formset:removed", function () {

        setTimeout(() => {
            actualizarSelects();
        }, 0);

    });
    cargarDetalles();

});
