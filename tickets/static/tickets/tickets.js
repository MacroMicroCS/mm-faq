/* Global ticket system JS — keyboard shortcuts, utilities */

// ── Keyboard Shortcuts ──────────────────────────────────────────
const SHORTCUTS = {
    'g i': () => { window.location.href = '/tickets/inbox'; },
    'g t': () => { window.location.href = '/tickets/templates'; },
    'g c': () => { window.location.href = '/tickets/customers'; },
    'g r': () => { window.location.href = '/tickets/reports'; },
    'n':   () => { document.getElementById('new-ticket-modal') && openNewTicketModal(); },
    '?':   () => { document.getElementById('shortcuts-modal').style.display = 'flex'; },
};

let keyBuffer = '';
let keyTimer = null;

document.addEventListener('keydown', (e) => {
    // Skip if typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    keyBuffer += (keyBuffer ? ' ' : '') + e.key;
    clearTimeout(keyTimer);
    keyTimer = setTimeout(() => { keyBuffer = ''; }, 800);

    if (SHORTCUTS[keyBuffer]) {
        e.preventDefault();
        SHORTCUTS[keyBuffer]();
        keyBuffer = '';
    } else if (e.key === 'Escape') {
        document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
        keyBuffer = '';
    }
});

// Close modal on backdrop click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.style.display = 'none';
    }
});

// ── Shortcuts Help Modal (injected on load) ──────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.createElement('div');
    modal.id = 'shortcuts-modal';
    modal.className = 'modal';
    modal.style.display = 'none';
    modal.innerHTML = `
    <div class="modal-box">
        <h2>鍵盤快捷鍵</h2>
        <table style="width:100%;border-collapse:collapse;font-size:0.88rem">
            <tr><td style="padding:5px 8px;color:#999">g i</td><td>前往收件匣</td></tr>
            <tr><td style="padding:5px 8px;color:#999">g t</td><td>前往模板庫</td></tr>
            <tr><td style="padding:5px 8px;color:#999">g c</td><td>前往客戶列表</td></tr>
            <tr><td style="padding:5px 8px;color:#999">g r</td><td>前往報表</td></tr>
            <tr><td style="padding:5px 8px;color:#999">n</td><td>新增 Ticket</td></tr>
            <tr><td style="padding:5px 8px;color:#999">?</td><td>顯示此說明</td></tr>
            <tr><td style="padding:5px 8px;color:#999">Esc</td><td>關閉彈窗</td></tr>
        </table>
        <div class="modal-actions">
            <button class="btn btn-primary" onclick="document.getElementById('shortcuts-modal').style.display='none'">關閉</button>
        </div>
    </div>`;
    document.body.appendChild(modal);
});
