/* ── Time-range toggle ─────────────────────────────────────────────────── */
document.querySelectorAll('.time-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelector('.time-btn.active')?.classList.remove('active');
        btn.classList.add('active');
    });
});

/* ── Sensor map canvas ─────────────────────────────────────────────────── */
const MOISTURE_COLOR = {
    low:     '#E53E3E',
    fair:    '#ED8936',
    good:   '#ECC94B',
    optimal: '#48BB78',
};

const NODE_R = 18;

function drawMap(canvas, nodes) {
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const pad = 4;

    // Map background
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#E8F5E9';
    ctx.strokeStyle = '#E8ECF0';
    ctx.lineWidth = 1;
    roundRect(ctx, pad, pad, w - pad * 2, h - pad * 2, 8);
    ctx.fill();
    ctx.stroke();

    // Draw each node
    const mapX = pad;
    const mapY = pad;
    const mapW = w - pad * 2;
    const mapH = h - pad * 2;

    nodes.forEach(node => {
        const cx = mapX + node.x * mapW;
        const cy = mapY + node.y * mapH;
        const color = MOISTURE_COLOR[node.moisture];

        // White outer ring
        ctx.beginPath();
        ctx.arc(cx, cy, NODE_R + 3, 0, Math.PI * 2);
        ctx.fillStyle = '#FFFFFF';
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();

        // Coloured fill
        ctx.beginPath();
        ctx.arc(cx, cy, NODE_R, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        // Label
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 8px "Segoe UI", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(node.id, cx, cy);
    });
}

function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
}

/* ── Init & resize ─────────────────────────────────────────────────────── */
function init() {
    const canvas = document.getElementById('sensorMap');
    if (!canvas) return;

    const nodes = JSON.parse(canvas.dataset.nodes);

    const draw = () => drawMap(canvas, nodes);
    draw();

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(draw, 60);
    });
}

document.addEventListener('DOMContentLoaded', init);
