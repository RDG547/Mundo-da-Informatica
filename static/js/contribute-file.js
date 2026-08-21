(function () {
    const form = document.getElementById('contributionForm');
    if (!form) return;
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const button = form.querySelector('[type="submit"]');
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando…';
        try {
            const response = await fetch('/contribuir-arquivo', { method: 'POST', headers: { 'X-CSRFToken': csrf }, body: new FormData(form) });
            const payload = await response.json();
            if (!response.ok || !payload.success) throw new Error(payload.message || 'Não foi possível enviar.');
            if (typeof window.showNotification === 'function') window.showNotification(payload.message, 'success');
            form.reset();
            window.location.reload();
        } catch (error) {
            if (typeof window.showNotification === 'function') window.showNotification(error.message, 'error');
            else window.alert(error.message);
        } finally {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-paper-plane"></i> Enviar contribuição';
        }
    });
})();
