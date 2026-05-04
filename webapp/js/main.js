/* ════════════════════════════════════════════════════════════════
   Muhabbat Atelier — WebApp v2
   Glass UI + Smooth motion + Telegram native integration
   ──────────────────────────────────────────────────────────────── */

// ─── Telegram WebApp ───────────────────────────────────────────────
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  try {
    tg.setHeaderColor('#F4EFE6');
    tg.setBackgroundColor('#F4EFE6');
    tg.enableClosingConfirmation();
  } catch (e) {}
}

const initData = tg?.initData || '';

// ─── API ───────────────────────────────────────────────────────────
const API = {
  async get(path) {
    const res = await fetch(path, {
      headers: { 'X-Telegram-Init-Data': initData },
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

// ─── Helpers ───────────────────────────────────────────────────────
const fmtMoney = (n) =>
  Math.round(n).toLocaleString('ru-RU').replace(/,/g, ' ') + " so'm";

const escHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c])
  );

// Haptics
const haptic = {
  light:   () => { try { tg?.HapticFeedback.impactOccurred('light');  } catch(e){} },
  medium:  () => { try { tg?.HapticFeedback.impactOccurred('medium'); } catch(e){} },
  heavy:   () => { try { tg?.HapticFeedback.impactOccurred('heavy');  } catch(e){} },
  success: () => { try { tg?.HapticFeedback.notificationOccurred('success'); } catch(e){} },
  warning: () => { try { tg?.HapticFeedback.notificationOccurred('warning'); } catch(e){} },
};

// Toast
const toastEl = document.getElementById('toast');
let toastTimer;
function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2400);
}


// ════════════════════════════════════════════════════════════════
// Three.js Hero — glass torus knot, soft particles, gentle motion
// ════════════════════════════════════════════════════════════════
(function initHero() {
  const canvas = document.getElementById('hero-canvas');
  if (!canvas || !window.THREE) return;

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  camera.position.set(0, 0, 5.5);

  const renderer = new THREE.WebGLRenderer({
    canvas, antialias: true, alpha: true,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;

  function resize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener('resize', resize);

  // ─ Lighting (3-point + ambient) ─
  const key = new THREE.DirectionalLight(0xffe9d4, 1.6);
  key.position.set(2, 3, 4);
  scene.add(key);

  const rim = new THREE.DirectionalLight(0xb85a2c, 0.85);
  rim.position.set(-3, -1, 2);
  scene.add(rim);

  const fill = new THREE.DirectionalLight(0xfbf8f2, 0.4);
  fill.position.set(0, -3, 3);
  scene.add(fill);

  const ambient = new THREE.AmbientLight(0xf4efe6, 0.5);
  scene.add(ambient);

  // ─ Hero: glass-iridescent torus knot ─
  const geom = new THREE.TorusKnotGeometry(0.9, 0.28, 240, 36, 2, 3);
  const mat = new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    metalness: 0.15,
    roughness: 0.08,
    clearcoat: 1.0,
    clearcoatRoughness: 0.15,
    iridescence: 0.95,
    iridescenceIOR: 1.45,
    iridescenceThicknessRange: [100, 800],
    sheen: 0.5,
    sheenColor: 0xe8a87c,
    sheenRoughness: 0.3,
    transmission: 0.0,        // mobile uchun og'irlik bermasin
    opacity: 0.92,
    transparent: true,
    side: THREE.DoubleSide,
  });
  const knot = new THREE.Mesh(geom, mat);
  scene.add(knot);

  // ─ Inner glow object (reflective core) ─
  const coreGeom = new THREE.IcosahedronGeometry(0.35, 1);
  const coreMat = new THREE.MeshPhysicalMaterial({
    color: 0xb85a2c,
    metalness: 0.95,
    roughness: 0.2,
    emissive: 0xb85a2c,
    emissiveIntensity: 0.2,
  });
  const core = new THREE.Mesh(coreGeom, coreMat);
  scene.add(core);

  // ─ Particle dust ─
  const pCount = 120;
  const pGeom = new THREE.BufferGeometry();
  const pos = new Float32Array(pCount * 3);
  for (let i = 0; i < pCount; i++) {
    const r = 1.9 + Math.random() * 2.0;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    pos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
    pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    pos[i * 3 + 2] = r * Math.cos(phi);
  }
  pGeom.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const pMat = new THREE.PointsMaterial({
    color: 0xb85a2c,
    size: 0.022,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.5,
    depthWrite: false,
  });
  scene.add(new THREE.Points(pGeom, pMat));

  // Second layer of particles, smaller, softer
  const pCount2 = 80;
  const pGeom2 = new THREE.BufferGeometry();
  const pos2 = new Float32Array(pCount2 * 3);
  for (let i = 0; i < pCount2; i++) {
    const r = 0.9 + Math.random() * 0.7;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    pos2[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
    pos2[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    pos2[i * 3 + 2] = r * Math.cos(phi);
  }
  pGeom2.setAttribute('position', new THREE.BufferAttribute(pos2, 3));
  const pMat2 = new THREE.PointsMaterial({
    color: 0xfff5e8,
    size: 0.014,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.7,
    depthWrite: false,
  });
  const innerDust = new THREE.Points(pGeom2, pMat2);
  scene.add(innerDust);

  // ─ Parallax (mouse + tilt) ─
  let tmx = 0, tmy = 0;
  let mx = 0, my = 0;

  window.addEventListener('mousemove', (e) => {
    tmx = (e.clientX / window.innerWidth - 0.5) * 0.5;
    tmy = (e.clientY / window.innerHeight - 0.5) * 0.4;
  });

  // Mobile tilt
  function handleOrient(e) {
    if (e.gamma == null || e.beta == null) return;
    tmx = Math.max(-1, Math.min(1, e.gamma / 45)) * 0.3;
    tmy = Math.max(-1, Math.min(1, (e.beta - 45) / 45)) * 0.25;
  }
  window.addEventListener('deviceorientation', handleOrient, { passive: true });

  // ─ Animate ─
  let t = 0;
  function tick() {
    t += 0.005;

    knot.rotation.x = t * 0.45;
    knot.rotation.y = t * 0.65;
    knot.position.y = Math.sin(t * 1.5) * 0.08;

    core.rotation.x = -t * 0.8;
    core.rotation.y = t * 1.1;
    core.position.x = Math.sin(t * 0.8) * 0.15;
    core.position.y = Math.cos(t * 0.6) * 0.15;

    innerDust.rotation.y = t * 0.2;

    mx += (tmx - mx) * 0.04;
    my += (tmy - my) * 0.04;
    camera.position.x = mx;
    camera.position.y = -my;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }
  tick();
})();


// ════════════════════════════════════════════════════════════════
// Cart
// ════════════════════════════════════════════════════════════════
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
    cartCount.textContent = Math.round(cartState.count);
    cartCount.classList.add('show');
  } else {
    cartCount.classList.remove('show');
  }

  // Telegram MainButton
  if (tg?.MainButton) {
    if (cartState.count > 0) {
      tg.MainButton.setText(`Buyurtma · ${fmtMoney(cartState.total)}`);
      tg.MainButton.color = '#1B1714';
      tg.MainButton.textColor = '#FFFDFA';
      tg.MainButton.show();
      tg.MainButton.enable();
    } else {
      tg.MainButton.hide();
    }
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
        <div class="cart-item-name">${escHtml(item.name)}</div>
        <div class="cart-item-meta">${fmtMoney(item.price)}</div>
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

cartItemsEl.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const id = parseInt(btn.dataset.id);
  const action = btn.dataset.action;
  const item = cartState.items.find((i) => i.product_id === id);
  if (!item) return;

  let newQty = item.quantity;
  if (action === 'inc') newQty++;
  else if (action === 'dec') newQty--;

  haptic.light();
  try {
    await API.post('/api/cart/update', { product_id: id, quantity: newQty });
    await loadCart();
  } catch (err) {
    haptic.warning();
    showToast('Xato yuz berdi');
  }
});

function openCart() {
  haptic.light();
  cartDrawer.classList.add('open');
  cartDrawer.setAttribute('aria-hidden', 'false');
  if (tg?.BackButton) {
    tg.BackButton.show();
    tg.BackButton.onClick(closeCart);
  }
}

function closeCart() {
  cartDrawer.classList.remove('open');
  cartDrawer.setAttribute('aria-hidden', 'true');
  if (tg?.BackButton) {
    tg.BackButton.hide();
  }
}

cartBtn.addEventListener('click', openCart);
cartClose.addEventListener('click', closeCart);
document.querySelector('.cart-backdrop').addEventListener('click', closeCart);

checkoutBtn.addEventListener('click', () => {
  haptic.medium();
  // Hozirgi versiyada — bot orqali davom etish
  showToast('Checkout botda davom etadi…');
  setTimeout(() => {
    tg?.close();
  }, 800);
});

// Telegram MainButton -> open cart
if (tg?.MainButton) {
  tg.MainButton.onClick(() => {
    if (cartDrawer.classList.contains('open')) {
      // Already open — checkout
      haptic.medium();
      showToast('Checkout botda davom etadi…');
      setTimeout(() => tg?.close(), 800);
    } else {
      openCart();
    }
  });
}

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


// ════════════════════════════════════════════════════════════════
// Products
// ════════════════════════════════════════════════════════════════
const grid = document.getElementById('products-grid');

async function loadProducts() {
  try {
    const data = await API.get('/api/products?featured=1');
    if (!data.products || data.products.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center;
                    color: var(--ink-3); font-style: italic;
                    font-family: var(--display); font-size: 18px;">
          Tez orada mahsulotlar paydo bo'ladi…
        </div>`;
      return;
    }

    grid.innerHTML = '';
    for (const p of data.products) {
      const card = document.createElement('div');
      card.className = 'product-card';
      const photoHTML = p.photo_file_id
        ? `<img src="${p.photo_file_id}" alt="${escHtml(p.name)}" />`
        : `<span class="product-image-placeholder">${escHtml(p.name[0] || '✦')}</span>`;

      card.innerHTML = `
        <div class="product-image">${photoHTML}</div>
        <div class="product-info">
          <div class="product-name">${escHtml(p.name)}</div>
          <div class="product-price">${fmtMoney(p.price)}</div>
          <div class="product-stock ${p.in_stock ? '' : 'out'}">
            ${p.in_stock ? `mavjud · ${p.stock} ${p.unit}` : 'mavjud emas'}
          </div>
          <button class="product-add" data-id="${p.id}" ${p.in_stock ? '' : 'disabled'}>
            <span>${p.in_stock ? "Savatga qo'shish" : 'Mavjud emas'}</span>
          </button>
        </div>
      `;
      grid.appendChild(card);
    }

    grid.querySelectorAll('.product-add').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id);
        haptic.light();
        btn.disabled = true;
        const span = btn.querySelector('span');
        try {
          await API.post('/api/cart/add', { product_id: id, quantity: 1 });
          btn.classList.add('added');
          if (span) span.textContent = "✓ Qo'shildi";
          haptic.success();
          await loadCart();
          setTimeout(() => {
            btn.classList.remove('added');
            if (span) span.textContent = "Savatga qo'shish";
            btn.disabled = false;
          }, 1600);
        } catch (err) {
          btn.disabled = false;
          haptic.warning();
          showToast("Qo'sha olmadik");
        }
      });
    });
  } catch (err) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--accent);">
        Yuklashda xato. Qayta urinib ko'ring.
      </div>`;
    console.error(err);
  }
}


// ════════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  loadProducts();
  loadCart();
});
