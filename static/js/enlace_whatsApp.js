document.addEventListener('DOMContentLoaded', function() {
    const button = document.getElementById('whatsapp-button');
    if (!button) return;

    const phone = button.dataset.whatsappNumber;
    if (!phone) return;

    button.addEventListener('click', function() {
        const rows = document.querySelectorAll('div.row.text-center.mt-3');
        const lines = [];

        rows.forEach(function(row) {
            const nameEl = row.querySelector('.col-7 .fw-bold');
            const qtyEl = row.querySelector('.cantidad .reservado div');
            const priceEl = row.querySelector('#value_precio') || row.querySelector('#value_costo');
            const name = nameEl ? nameEl.textContent.trim() : '';
            const qty = qtyEl ? qtyEl.textContent.trim() : '';
            const price = priceEl ? priceEl.textContent.trim() : '';

            if (name) {
                lines.push(name + ' x ' + qty + ' - ' + price);
            }
        });

        const totalEl = document.querySelector('.cart-summary__total-amount');
        const total = totalEl ? totalEl.textContent.trim() : '';

        let message = 'Consulta de pedido:\n';
        if (lines.length) {
            message += lines.join('\n') + '\n';
        }
        if (total) {
            message += 'Total: ' + total;
        }

        const url = 'https://wa.me/' + encodeURIComponent(phone) + '?text=' + encodeURIComponent(message);
        window.open(url, '_blank');
    });
});
