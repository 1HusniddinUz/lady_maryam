/* ════════════════════════════════════════════════════════════════
   Muhabbat Atelier — WebApp Logic
   ──────────────────────────────────────────────────────────────── */

// ─── Telegram WebApp init ──────────────────────────────────────────
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  // Bizning rang sxemamizdan foydalanish, Telegram tema rangini yo'qotish
  try {
    tg.setHeaderColor('#F5F1EA');
    tg.setBackgroundColor('#F5F1EA');
  } catch (e) {}
}

const initData = tg?.initData || '';
const tgUser = tg?.initDataUnsafe?.user;

// ─── API Helper ─────────────────────────────────────────────────────
const API = {
  async get(path) {
    const res = await fetch(path, {
      headers: { 'X-Telegram-Init-Data': initData }
    });
    if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
    return res.json();
  },
  async post(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
      },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
    return res.json();
  },
};

// ─── Format ────────────────────────────────────────────────────────
function fmtMoney(num) {
  return Math.round(num).toLocaleString('ru-RU').replace(/,/g, ' ') + " so'm";
}

// ─── Toast ─────────────────────────────────────────────────────────
const toast = document.getElementById('toast');
let toastTimer;
function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2400);
}

// ─── Haptic ────────────────────────────────────────────────────────
function hapticLight()  { try { tg?.HapticFeedback.impactOccurred('light');  } catch (e) {} }
function hapticMedium() { try { tg?.HapticFeedback.impactOccurred('medium'); } catch (e) {} }
function hapticSuccess(){ try { tg?.HapticFeedback.notificationOccurred('success'); } catch (e) {} }

// ─── Three.js Hero Scene ───────────────────────────────────────────
// Pearlescent torus knot - sokin lyuks atmosfera

(function initHero() {
  const canvas = document.getElementById('hero-canvas');
  if (!canvas || !window.THREE) return;

  const scene = new THREE.Scene();
  // No fog - keep it clean

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 5);

  const renderer = new THREE.WebGLRenderer({
    canvas, antialias: true, alpha: true,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);

  function resize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener('resize', resize);

  // Lighting - soft three-point setup
  const keyLight = new THREE.DirectionalLight(0xfff5e8, 1.4);
  keyLight.position.set(2, 3, 4);
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0xb85a2c, 0.5);  // accent rim
  fillLight.position.set(-3, -1, 2);
  scene.add(fillLight);

  const ambient = new THREE.AmbientLight(0xf5f1ea, 0.6);
  scene.add(ambient);

  // Hero object: Stylized torus knot, pearlescent
  const knotGeom = new THREE.TorusKnotGeometry(0.85, 0.27, 220, 32, 2, 3);
  const knotMat = new THREE.MeshPhysicalMaterial({
    color: 0xf3ebdf,
    metalness: 0.45,
    roughness: 0.18,
    clearcoat: 0.8,
    clearcoatRoughness: 0.25,
    iridescence: 0.7,
    iridescenceIOR: 1.4,
    sheen: 0.6,
    sheenColor: 0xe8a87c,
    sheenRoughness: 0.4,
  });
  const knot = new THREE.Mesh(knotGeom, knotMat);
  scene.add(knot);

  // Subtle orbiting particles (dust)
  const particleCount = 80;
  const pGeom = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  const sizes = new Float32Array(particleCount);
  for (let i = 0; i < particleCount; i++) {
    // Distribute on a sphere around the knot
    const r = 1.8 + Math.random() * 1.6;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = r * Math.cos(phi);
    sizes[i] = 0.012 + Math.random() * 0.018;
  }
  pGeom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const pMat = new THREE.PointsMaterial({
    color: 0xb85a2c,
    size: 0.025,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.45,
    depthWrite: false,
  });
  const particles = new THREE.Points(pGeom, pMat);
  scene.add(particles);

  // Mouse parallax
  let mx = 0, my = 0;
  let tmx = 0, tmy = 0;
  window.addEventListener('mousemove', (e) => {
    tmx = (e.clientX / window.innerWidth - 0.5) * 0.4;
    tmy = (e.clientY / window.innerHeight - 0.5) * 0.3;
  });

  // Touch parallax (mobile)
  window.addEventListener('deviceorientation', (e) => {
    if (e.gamma !== null && e.beta !== null) {
      tmx = (e.gamma / 90) * 0.3;
      tmy = (e.beta / 180) * 0.3;
    }
  }, { passive: true });

  // Animate
  let t = 0;
  function tick() {
    t += 0.005;

    // Knot rotation - slow, organic
    knot.rotation.x = t * 0.5;
    knot.rotation.y = t * 0.7;
    knot.position.y = Math.sin(t * 1.5) * 0.08;

    // Particles slow drift
    particles.rotation.y = t * 0.15;
    particles.rotation.x = t * 0.08;

    // Smooth parallax
    mx += (tmx - mx) * 0.05;
    my += (tmy - my) * 0.05;
    camera.position.x = mx;
    camera.position.y = -my;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }
  tick();
})();


// ─── Cart State ────────────────────────────────────────────────────
let cartState = { items: [], total: 0, count: 0 };

const cartBtn      = document.getElementById('cart-btn');
const cartCount    = document.getElementById('cart-count');
const cartDrawer   = document.getElementById('cart-drawer');
const cartClose    = document.getElementById('cart-close');
const cartItemsEl  = document.getElementById('cart-items');
const cartEmpty    = document.getElementById('cart-empty');
const cartFooter   = document.getElementById('cart-footer');
const cartTotalAmt = document.getElementById('cart-total-amount');
const checkoutBtn  = document.getElementById('checkout-btn');

function updateCartBadge() {
  if (cartState.count > 0) {
    cartCount.textContent = cartState.count;
    cartCount.classList.add('show');
  } else {
    cartCount.classList.remove('show');
  }
}

function renderCart() {
  cartItemsEl.innerHTML = '';
  if (cartState.items.length === 0) {
    cartEmpty.classList.remove('hidden');
    cartFooter.hidden = true;
    return;
  }
  cartEmpty.classList.add('hidden');
  cartFooter.hidden = false;

  for (const item of cartState.items) {
    const div = document.createElement('div');
    div.className = 'cart-item';
    div.innerHTML = `
      <div class="cart-item-img">
        ${item.photo ? `<img src="${item.photo}" alt=""/>` : '✦'}
      </div>
      <div class="cart-item-info">
        <div class="cart-item-name">${escapeHtml(item.name)}</div>
        <div class="cart-item-meta">${fmtMoney(item.price)} × ${item.quantity}</div>
      </div>
      <div class="cart-item-controls">
        <button class="cart-qty-btn" data-action="dec" data-id="${item.product_id}">−</button>
        <span class="cart-qty-num">${item.quantity}</span>
        <button class="cart-qty-btn" data-action="inc" data-id="${item.product_id}">+</button>
      </div>
    `;
    cartItemsEl.appendChild(div);
  }
  cartTotalAmt.textContent = fmtMoney(cartState.total);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

cartItemsEl.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const id = parseInt(btn.dataset.id);
  const action = btn.dataset.action;
  const item = cartState.items.find(i => i.product_id === id);
  if (!item) return;

  let newQty = item.quantity;
  if (action === 'inc') newQty++;
  else if (action === 'dec') newQty--;

  hapticLight();
  try {
    await API.post('/api/cart/update', { product_id: id, quantity: newQty });
    await loadCart();
  } catch (err) {
    showToast('Xato yuz berdi');
  }
});

cartBtn.addEventListener('click', () => {
  hapticLight();
  cartDrawer.classList.add('open');
});
cartClose.addEventListener('click', () => cartDrawer.classList.remove('open'));
document.querySelector('.cart-backdrop')?.addEventListener('click', () => {
  cartDrawer.classList.remove('open');
});

checkoutBtn.addEventListener('click', () => {
  hapticMedium();
  // Hozirgi versiyada Telegram bot orqali checkout
  tg?.close();
  showToast("Checkout botda ochiladi (keyingi versiyada to'g'ridan-to'g'ri)");
});


// ─── Load Cart from API ────────────────────────────────────────────
async function loadCart() {
  try {
    const data = await API.get('/api/cart');
    cartState = data;
    updateCartBadge();
    renderCart();
  } catch (err) {
    console.error('Cart load error:', err);
  }
}


// ─── Load Products ─────────────────────────────────────────────────
const grid = document.getElementById('products-grid');

async function loadProducts() {
  try {
    const data = await API.get('/api/products?featured=1');
    if (!data.products || data.products.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; color: var(--ink-soft); font-style: italic; font-family: var(--display); font-size: 18px;">
          Tez orada mahsulotlar paydo bo'ladi…
        </div>
      `;
      return;
    }

    grid.innerHTML = '';
    for (const p of data.products) {
      const card = document.createElement('div');
      card.className = 'product-card';
      const photoHTML = p.photo_file_id
        ? `<img src="${p.photo_file_id}" alt="${escapeHtml(p.name)}" />`
        : `<span class="product-image-placeholder">${escapeHtml(p.name[0] || '✦')}</span>`;

      card.innerHTML = `
        <div class="product-image">${photoHTML}</div>
        <div class="product-info">
          <div class="product-name">${escapeHtml(p.name)}</div>
          <div class="product-price">${fmtMoney(p.price)}</div>
          <div class="product-stock ${p.in_stock ? '' : 'out'}">
            ${p.in_stock ? `mavjud · ${p.stock} ${p.unit}` : 'mavjud emas'}
          </div>
          <button class="product-add" data-id="${p.id}" ${p.in_stock ? '' : 'disabled'}>
            ${p.in_stock ? "Savatga qo'shish" : 'Mavjud emas'}
          </button>
        </div>
      `;
      grid.appendChild(card);
    }

    // Add to cart handlers
    grid.querySelectorAll('.product-add').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id);
        hapticLight();
        btn.disabled = true;
        try {
          await API.post('/api/cart/add', { product_id: id, quantity: 1 });
          btn.classList.add('added');
          btn.textContent = '✓ Qo\'shildi';
          hapticSuccess();
          showToast('Savatga qo\'shildi');
          await loadCart();
          setTimeout(() => {
            btn.classList.remove('added');
            btn.textContent = "Savatga qo'shish";
            btn.disabled = false;
          }, 1500);
        } catch (err) {
          btn.disabled = false;
          showToast('Qo\'sha olmadik');
        }
      });
    });
  } catch (err) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--accent);">
        Yuklashda xato. Qayta urinib ko'ring.
      </div>
    `;
  }
}


// ─── INIT ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadProducts();
  loadCart();
});
