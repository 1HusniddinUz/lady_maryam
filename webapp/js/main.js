/* ════════════════════════════════════════════════════════════════
   Lady Maryam Atelier — SPA v4
   Multi-view router + Wishlist + Smooth transitions
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
const tgUser = tg?.initDataUnsafe?.user;

// ─── API ───────────────────────────────────────────────────────────
const API = {
  async get(path) {
    const res = await fetch(path, { headers: { 'X-Telegram-Init-Data': initData } });
    if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
    return res.json();
  },
  async post(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': initData },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `API ${path}: ${res.status}`);
    return data;
  },
};

// ─── Helpers ───────────────────────────────────────────────────────
const fmtMoney = (n) => Math.round(n).toLocaleString('ru-RU').replace(/,/g, ' ') + " so'm";
const escHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));

const haptic = {
  light:   () => { try { tg?.HapticFeedback.impactOccurred('light'); } catch(e){} },
  medium:  () => { try { tg?.HapticFeedback.impactOccurred('medium'); } catch(e){} },
  success: () => { try { tg?.HapticFeedback.notificationOccurred('success'); } catch(e){} },
  warning: () => { try { tg?.HapticFeedback.notificationOccurred('warning'); } catch(e){} },
  error:   () => { try { tg?.HapticFeedback.notificationOccurred('error'); } catch(e){} },
};

const toastEl = document.getElementById('toast');
let toastTimer;
function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2400);
}

const fmtDate = (iso) => {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('uz-UZ', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch (e) { return iso; }
};

const wishHeartSVG = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`;


// ════════════════════════════════════════════════════════════════
// State
// ════════════════════════════════════════════════════════════════
const state = {
  cart: { items: [], total: 0, count: 0 },
  wishlist: new Set(),
  shop: { name: 'Lady Maryam', phone: '', address: '' },
  currentView: null,
  currentParams: null,
  history: [],
};


// ════════════════════════════════════════════════════════════════
// Router
// ════════════════════════════════════════════════════════════════
const appContent = document.getElementById('app-content');

async function navigate(view, params = null, options = {}) {
  haptic.light();

  // History tracking
  if (!options.fromHistory && state.currentView) {
    state.history.push({ view: state.currentView, params: state.currentParams });
  }

  // Exit animation
  const currentEl = appContent.querySelector('.view');
  if (currentEl) {
    currentEl.classList.remove('active');
    currentEl.classList.add('exiting');
    await new Promise(r => setTimeout(r, 200));
  }

  // Render new view
  state.currentView = view;
  state.currentParams = params;

  appContent.innerHTML = '';
  const viewEl = document.createElement('div');
  viewEl.className = 'view';
  appContent.appendChild(viewEl);

  // Scroll to top
  window.scrollTo(0, 0);

  // Render based on view name
  try {
    switch (view) {
      case 'home':     await renderHome(viewEl); break;
      case 'catalog':  await renderCatalog(viewEl); break;
      case 'product':  await renderProduct(viewEl, params?.id); break;
      case 'orders':   await renderOrders(viewEl); break;
      case 'wishlist': await renderWishlist(viewEl); break;
      default: viewEl.innerHTML = '<div class="empty-state"><p>Sahifa topilmadi</p></div>';
    }
  } catch (err) {
    console.error('Render error:', err);
    viewEl.innerHTML = `<div class="empty-state"><div class="empty-state-icon">!</div><h3 class="empty-state-title">Xato</h3><p class="empty-state-text">${escHtml(err.message)}</p></div>`;
  }

  // Enter animation
  requestAnimationFrame(() => {
    viewEl.classList.add('active');
  });

  // Telegram BackButton
  updateBackButton();
}

function goBack() {
  if (state.history.length === 0) {
    navigate('home', null, { fromHistory: true });
    return;
  }
  const prev = state.history.pop();
  navigate(prev.view, prev.params, { fromHistory: true });
}

function updateBackButton() {
  if (!tg?.BackButton) return;
  if (state.currentView !== 'home' && !document.querySelector('.cart-drawer.open') && !document.querySelector('.sheet.open')) {
    tg.BackButton.show();
    tg.BackButton.onClick(goBack);
  } else if (state.currentView === 'home') {
    tg.BackButton.hide();
  }
}

// Global click handler for nav-data
document.addEventListener('click', (e) => {
  const navBtn = e.target.closest('[data-nav]');
  if (navBtn) {
    e.preventDefault();
    const view = navBtn.dataset.nav;
    const params = navBtn.dataset.id ? { id: parseInt(navBtn.dataset.id) } : null;
    navigate(view, params);
  }
});


// ════════════════════════════════════════════════════════════════
// VIEW: HOME
// ════════════════════════════════════════════════════════════════
async function renderHome(viewEl) {
  viewEl.innerHTML = `
    <section class="hero">
      <canvas id="hero-canvas" class="hero-canvas"></canvas>
      <div class="hero-content">
        <p class="hero-eyebrow">Atelier · Shofirkon</p>
        <h1 class="hero-title">Sokin <em>nafosat</em><br/>— har bir libosda.</h1>
        <p class="hero-sub">Sifatli matolar, mukammal tikish, vaqt sinovidan o'tgan dizayn.</p>
        <button class="hero-cta" data-nav="catalog">
          <span>Kolleksiyani ko'rish</span>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h8M7 3l4 4-4 4"/></svg>
        </button>
      </div>
    </section>

    <section class="nav-tiles">
      <button class="nav-tile" data-nav="catalog">
        <span class="nav-tile-icon">📦</span>
        <span class="nav-tile-title">Katalog</span>
        <span class="nav-tile-meta">Barcha mahsulotlar</span>
        <span class="nav-tile-arrow">→</span>
      </button>
      <button class="nav-tile" data-nav="orders">
        <span class="nav-tile-icon">📋</span>
        <span class="nav-tile-title">Buyurtmalarim</span>
        <span class="nav-tile-meta">Tarix · status</span>
        <span class="nav-tile-arrow">→</span>
      </button>
      <button class="nav-tile" data-nav="wishlist">
        <span class="nav-tile-icon">♥</span>
        <span class="nav-tile-title">Sevimlilar</span>
        <span class="nav-tile-meta">Tanlanganlar</span>
        <span class="nav-tile-arrow">→</span>
      </button>
      <a class="nav-tile" href="tel:${state.shop.phone || ''}">
        <span class="nav-tile-icon">📞</span>
        <span class="nav-tile-title">Bog'lanish</span>
        <span class="nav-tile-meta">${escHtml(state.shop.phone || '+998')}</span>
        <span class="nav-tile-arrow">→</span>
      </a>
    </section>

    <section class="featured">
      <div class="section-head">
        <p class="section-eyebrow">— hozir mashhur</p>
        <h2 class="section-title">Tanlangan asarlar</h2>
      </div>
      <div id="featured-grid" class="products-grid">
        <div class="product-skeleton"></div>
        <div class="product-skeleton"></div>
        <div class="product-skeleton"></div>
        <div class="product-skeleton"></div>
      </div>
    </section>

    <section class="manifest">
      <div class="manifest-line"></div>
      <p class="manifest-quote">«Liboslar shunchaki kiyim emas — ular hikoya, his va xotira.»</p>
      <p class="manifest-author">— Lady Maryam Atelier</p>
    </section>

    <section class="contact">
      <div class="contact-card">
        <p class="contact-eyebrow">— Bog'lanish</p>
        <h3 class="contact-title">Tashrif buyurishingiz mumkin</h3>
        <div class="contact-details">
          <div class="contact-row"><span class="contact-icon">📍</span><span>${escHtml(state.shop.address || '')}</span></div>
          <div class="contact-row"><span class="contact-icon">📞</span><a href="tel:${state.shop.phone || ''}">${escHtml(state.shop.phone || '')}</a></div>
        </div>
      </div>
    </section>

    <footer class="ftr">
      <p class="ftr-mark">lady maryam <span>✦</span> 2026</p>
      <p class="ftr-note">Shofirkon · Sof tikuv · Cheklanmagan e'tibor</p>
    </footer>
  `;

  initHero();
  loadFeatured();
}

async function loadFeatured() {
  const grid = document.getElementById('featured-grid');
  if (!grid) return;
  try {
    const data = await API.get('/api/products?featured=1');
    grid.innerHTML = '';
    if (!data.products?.length) {
      grid.innerHTML = `<div style="grid-column:1/-1;padding:60px 20px;text-align:center;color:var(--ink-3);font-style:italic;font-family:var(--display);font-size:18px;">Tez orada mahsulotlar paydo bo'ladi…</div>`;
      return;
    }
    data.products.forEach(p => grid.appendChild(makeProductCard(p)));
  } catch (err) {
    grid.innerHTML = `<div style="grid-column:1/-1;padding:40px;text-align:center;color:var(--accent);">${escHtml(err.message)}</div>`;
  }
}


// ════════════════════════════════════════════════════════════════
// VIEW: CATALOG
// ════════════════════════════════════════════════════════════════
let catalogState = { search: '', category: '', sort: 'newest' };

async function renderCatalog(viewEl) {
  viewEl.innerHTML = `
    <div class="view-page">
      <div class="page-head">
        <h1 class="page-title">Katalog</h1>
        <p class="page-sub">Barcha mahsulotlarimiz</p>
      </div>

      <div class="search-bar">
        <span class="search-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/>
          </svg>
        </span>
        <input id="search-input" type="search" placeholder="Mahsulot qidirish..." value="${escHtml(catalogState.search)}" />
        <button class="search-clear" id="search-clear">✕</button>
      </div>

      <div id="filter-row" class="filter-row">
        <button class="filter-chip active" data-cat="">Hammasi</button>
      </div>

      <div class="sort-row">
        <span class="sort-count" id="sort-count">Yuklanmoqda...</span>
        <select class="sort-select" id="sort-select">
          <option value="newest">Yangi</option>
          <option value="price_asc">Narx: arzon</option>
          <option value="price_desc">Narx: qimmat</option>
          <option value="name">Nomi (A-Z)</option>
        </select>
      </div>

      <div id="catalog-grid" class="products-grid">
        <div class="product-skeleton"></div>
        <div class="product-skeleton"></div>
        <div class="product-skeleton"></div>
        <div class="product-skeleton"></div>
      </div>
    </div>
  `;

  await loadCategories();

  const searchInput = document.getElementById('search-input');
  const searchClear = document.getElementById('search-clear');
  const sortSelect = document.getElementById('sort-select');

  sortSelect.value = catalogState.sort;

  let searchTimer;
  searchInput.addEventListener('input', () => {
    catalogState.search = searchInput.value;
    searchClear.classList.toggle('show', !!searchInput.value);
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadCatalog, 300);
  });
  searchClear.addEventListener('click', () => {
    searchInput.value = '';
    catalogState.search = '';
    searchClear.classList.remove('show');
    loadCatalog();
  });
  if (searchInput.value) searchClear.classList.add('show');

  sortSelect.addEventListener('change', () => {
    catalogState.sort = sortSelect.value;
    haptic.light();
    loadCatalog();
  });

  loadCatalog();
}

async function loadCategories() {
  try {
    const data = await API.get('/api/categories');
    const row = document.getElementById('filter-row');
    if (!row) return;
    data.categories.forEach(c => {
      const chip = document.createElement('button');
      chip.className = 'filter-chip';
      chip.dataset.cat = c.id;
      chip.textContent = c.name;
      if (String(catalogState.category) === String(c.id)) chip.classList.add('active');
      else if (!catalogState.category && c.id === '') chip.classList.add('active');
      row.appendChild(chip);
    });

    row.addEventListener('click', (e) => {
      const chip = e.target.closest('.filter-chip');
      if (!chip) return;
      row.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      catalogState.category = chip.dataset.cat;
      haptic.light();
      loadCatalog();
    });
  } catch (err) {
    console.error('Categories error:', err);
  }
}

async function loadCatalog() {
  const grid = document.getElementById('catalog-grid');
  const countEl = document.getElementById('sort-count');
  if (!grid) return;

  // Show skeletons
  grid.innerHTML = '';
  for (let i = 0; i < 4; i++) {
    const sk = document.createElement('div');
    sk.className = 'product-skeleton';
    grid.appendChild(sk);
  }

  try {
    const params = new URLSearchParams();
    if (catalogState.search) params.set('search', catalogState.search);
    if (catalogState.category) params.set('category_id', catalogState.category);
    if (catalogState.sort) params.set('sort', catalogState.sort);

    const data = await API.get('/api/products?' + params.toString());
    grid.innerHTML = '';

    if (countEl) {
      countEl.textContent = `${data.products.length} ta natija`;
    }

    if (!data.products?.length) {
      grid.innerHTML = `
        <div style="grid-column:1/-1;">
          <div class="empty-state">
            <div class="empty-state-icon">∅</div>
            <h3 class="empty-state-title">Topilmadi</h3>
            <p class="empty-state-text">Filtringizga mos mahsulot topilmadi. Boshqa qidiruv yoki kategoriyani tanlang.</p>
          </div>
        </div>
      `;
      return;
    }

    data.products.forEach(p => grid.appendChild(makeProductCard(p)));
  } catch (err) {
    grid.innerHTML = `<div style="grid-column:1/-1;padding:40px;text-align:center;color:var(--accent);">${escHtml(err.message)}</div>`;
  }
}


// ════════════════════════════════════════════════════════════════
// VIEW: PRODUCT DETAIL
// ════════════════════════════════════════════════════════════════
async function renderProduct(viewEl, productId) {
  if (!productId) {
    viewEl.innerHTML = `<div class="empty-state"><p>Mahsulot topilmadi</p></div>`;
    return;
  }

  viewEl.innerHTML = `
    <div class="detail-page">
      <button class="detail-back" id="detail-back" aria-label="Orqaga">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 12L6 8l4-4"/></svg>
      </button>

      <div class="detail-image-wrap">
        <div class="detail-image-placeholder">…</div>
      </div>

      <div class="detail-content" id="detail-content">
        <p class="page-sub" style="margin-bottom:16px;">Yuklanmoqda...</p>
      </div>
    </div>
  `;

  document.getElementById('detail-back').addEventListener('click', goBack);

  try {
    const p = await API.get(`/api/products/${productId}`);
    const isInWishlist = state.wishlist.has(p.id);
    const imgWrap = viewEl.querySelector('.detail-image-wrap');

    imgWrap.innerHTML = '';
    if (p.photo_url) {
      const img = document.createElement('img');
      img.src = p.photo_url;
      img.alt = p.name;
      img.onerror = () => {
        imgWrap.innerHTML = `<div class="detail-image-placeholder">${escHtml(p.name[0] || '✦')}</div>`;
      };
      imgWrap.appendChild(img);
    } else {
      imgWrap.innerHTML = `<div class="detail-image-placeholder">${escHtml(p.name[0] || '✦')}</div>`;
    }

    // Wishlist heart on image
    const wishBtn = document.createElement('button');
    wishBtn.className = 'detail-wish' + (isInWishlist ? ' active' : '');
    wishBtn.innerHTML = wishHeartSVG;
    wishBtn.addEventListener('click', async () => {
      haptic.medium();
      try {
        const r = await API.post('/api/wishlist/toggle', { product_id: p.id });
        if (r.in_wishlist) {
          state.wishlist.add(p.id);
          wishBtn.classList.add('active');
          showToast('Sevimlilarga qo\'shildi');
        } else {
          state.wishlist.delete(p.id);
          wishBtn.classList.remove('active');
          showToast('Sevimlilardan olindi');
        }
        updateWishlistBadge();
      } catch (err) {
        haptic.error();
        showToast(err.message);
      }
    });
    imgWrap.appendChild(wishBtn);

    // Image overlay
    const overlay = document.createElement('div');
    overlay.className = 'detail-image-overlay';
    imgWrap.appendChild(overlay);

    // Content
    const content = document.getElementById('detail-content');
    content.innerHTML = `
      ${p.category_name ? `<p class="detail-cat">${escHtml(p.category_name)}</p>` : ''}
      <h1 class="detail-name">${escHtml(p.name)}</h1>
      <div class="detail-price-row">
        <div class="detail-price">${fmtMoney(p.price)}</div>
        <div class="detail-stock-pill ${p.in_stock ? 'in' : ''}">${p.in_stock ? `✓ Mavjud` : '✕ Yo\'q'}</div>
      </div>
      ${p.description ? `<p class="detail-desc">${escHtml(p.description)}</p>` : ''}
    `;

    // Fixed bottom action bar
    const fab = document.createElement('div');
    fab.className = 'detail-fab-bar';
    fab.innerHTML = `
      <button class="btn-ghost ${isInWishlist ? 'active' : ''}" id="detail-wish-fab" aria-label="Sevimlilar">${wishHeartSVG}</button>
      <button class="btn-primary" id="detail-add-btn" ${p.in_stock ? '' : 'disabled'}>
        <span>${p.in_stock ? "Savatga qo'shish" : 'Mavjud emas'}</span>
      </button>
    `;
    viewEl.querySelector('.detail-page').appendChild(fab);

    document.getElementById('detail-wish-fab').addEventListener('click', () => wishBtn.click());
    document.getElementById('detail-add-btn').addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      const span = btn.querySelector('span');
      btn.disabled = true;
      haptic.medium();
      try {
        await API.post('/api/cart/add', { product_id: p.id, quantity: 1 });
        if (span) span.textContent = "✓ Qo'shildi";
        haptic.success();
        await loadCart();
        setTimeout(() => {
          if (span) span.textContent = "Savatga qo'shish";
          btn.disabled = false;
        }, 1600);
      } catch (err) {
        btn.disabled = false;
        haptic.error();
        showToast(err.message);
      }
    });
  } catch (err) {
    viewEl.querySelector('.detail-content').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">!</div>
        <h3 class="empty-state-title">Topilmadi</h3>
        <p class="empty-state-text">Bu mahsulot mavjud emas yoki o'chirib tashlangan.</p>
      </div>
    `;
  }
}


// ════════════════════════════════════════════════════════════════
// VIEW: ORDERS
// ════════════════════════════════════════════════════════════════
async function renderOrders(viewEl) {
  viewEl.innerHTML = `
    <div class="view-page">
      <div class="page-head">
        <h1 class="page-title">Buyurtmalarim</h1>
        <p class="page-sub">Sizning xaridlar tarixingiz</p>
      </div>
      <div id="orders-list" class="orders-list">
        <div class="product-skeleton" style="aspect-ratio:auto;height:160px;"></div>
        <div class="product-skeleton" style="aspect-ratio:auto;height:160px;"></div>
      </div>
    </div>
  `;

  try {
    const data = await API.get('/api/orders/my');
    const list = document.getElementById('orders-list');
    list.innerHTML = '';

    if (!data.orders?.length) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📦</div>
          <h3 class="empty-state-title">Hali buyurtmalar yo'q</h3>
          <p class="empty-state-text">Birinchi buyurtmangizni qiling — bu yerda ko'rinadi.</p>
          <button class="btn-primary" data-nav="catalog"><span>Katalogga o'tish</span></button>
        </div>
      `;
      return;
    }

    data.orders.forEach((o, idx) => {
      const card = document.createElement('div');
      card.className = 'order-card';
      card.style.animationDelay = `${idx * 0.05}s`;

      const itemImagesHTML = o.items.slice(0, 4).map(it => `
        <div class="order-mini-img">
          ${it.photo ? `<img src="${it.photo}" alt="" loading="lazy" onerror="this.style.display='none'"/>` : escHtml(it.name[0] || '✦')}
        </div>
      `).join('');

      card.innerHTML = `
        <div class="order-head">
          <div>
            <div class="order-id">Buyurtma #${o.id}</div>
            <div class="order-date">${fmtDate(o.created_at)}</div>
          </div>
          <span class="status-badge status-${o.status}">${escHtml(o.status)}</span>
        </div>
        <div class="order-items-mini">${itemImagesHTML}</div>
        <div class="order-foot">
          <span class="order-meta">${Math.round(o.items_count)} ta mahsulot</span>
          <span class="order-total">${fmtMoney(o.total_amount)}</span>
        </div>
      `;
      list.appendChild(card);
    });
  } catch (err) {
    document.getElementById('orders-list').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">!</div>
        <p class="empty-state-text">${escHtml(err.message)}</p>
      </div>
    `;
  }
}


// ════════════════════════════════════════════════════════════════
// VIEW: WISHLIST
// ════════════════════════════════════════════════════════════════
async function renderWishlist(viewEl) {
  viewEl.innerHTML = `
    <div class="view-page">
      <div class="page-head">
        <h1 class="page-title">Sevimlilar</h1>
        <p class="page-sub">Tanlanganlaringiz</p>
      </div>
      <div id="wishlist-grid" class="products-grid">
        <div class="product-skeleton"></div>
        <div class="product-skeleton"></div>
      </div>
    </div>
  `;

  try {
    const data = await API.get('/api/wishlist');
    const grid = document.getElementById('wishlist-grid');
    grid.innerHTML = '';

    // Update wishlist set
    state.wishlist = new Set(data.ids);
    updateWishlistBadge();

    if (!data.products?.length) {
      grid.innerHTML = `
        <div style="grid-column:1/-1;">
          <div class="empty-state">
            <div class="empty-state-icon">♥</div>
            <h3 class="empty-state-title">Hali bo'sh</h3>
            <p class="empty-state-text">Mahsulot ustida ♥ ni bosing — bu yerda saqlanadi.</p>
            <button class="btn-primary" data-nav="catalog"><span>Katalogga o'tish</span></button>
          </div>
        </div>
      `;
      return;
    }

    data.products.forEach(p => grid.appendChild(makeProductCard(p)));
  } catch (err) {
    document.getElementById('wishlist-grid').innerHTML = `
      <div class="empty-state"><p>${escHtml(err.message)}</p></div>
    `;
  }
}


// ════════════════════════════════════════════════════════════════
// PRODUCT CARD FACTORY
// ════════════════════════════════════════════════════════════════
function makeProductCard(p) {
  const card = document.createElement('div');
  card.className = 'product-card';

  const photoHTML = p.photo_url
    ? `<img src="${p.photo_url}" alt="${escHtml(p.name)}" loading="lazy" onerror="this.style.display='none'"/>`
    : '';
  const placeholderHTML = `<span class="product-image-placeholder">${escHtml(p.name[0] || '✦')}</span>`;

  const isInWishlist = state.wishlist.has(p.id);

  card.innerHTML = `
    <div class="product-image">
      ${p.photo_url ? photoHTML : placeholderHTML}
      <button class="product-wish-btn ${isInWishlist ? 'active' : ''}" data-wish="${p.id}" aria-label="Sevimlilar">
        ${wishHeartSVG}
      </button>
    </div>
    <div class="product-info" data-nav="product" data-id="${p.id}">
      <div class="product-name">${escHtml(p.name)}</div>
      <div class="product-price">${fmtMoney(p.price)}</div>
      <div class="product-stock ${p.in_stock ? '' : 'out'}">${p.in_stock ? `mavjud · ${p.stock} ${p.unit}` : 'mavjud emas'}</div>
      <button class="product-add" data-add="${p.id}" ${p.in_stock ? '' : 'disabled'}>
        <span>${p.in_stock ? "Savatga qo'shish" : 'Mavjud emas'}</span>
      </button>
    </div>
  `;

  // Wishlist toggle
  card.querySelector('[data-wish]').addEventListener('click', async (e) => {
    e.stopPropagation();
    e.preventDefault();
    const btn = e.currentTarget;
    haptic.light();
    try {
      const r = await API.post('/api/wishlist/toggle', { product_id: p.id });
      if (r.in_wishlist) {
        state.wishlist.add(p.id);
        btn.classList.add('active');
      } else {
        state.wishlist.delete(p.id);
        btn.classList.remove('active');
      }
      updateWishlistBadge();
    } catch (err) {
      haptic.error();
      showToast(err.message);
    }
  });

  // Add to cart
  card.querySelector('[data-add]').addEventListener('click', async (e) => {
    e.stopPropagation();
    e.preventDefault();
    const btn = e.currentTarget;
    const span = btn.querySelector('span');
    btn.disabled = true;
    haptic.light();
    try {
      await API.post('/api/cart/add', { product_id: p.id, quantity: 1 });
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
      haptic.error();
      showToast(err.message);
    }
  });

  return card;
}


// ════════════════════════════════════════════════════════════════
// THREE.JS HERO
// ════════════════════════════════════════════════════════════════
function initHero() {
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
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  resize();
  const resizeHandler = () => resize();
  window.addEventListener('resize', resizeHandler);

  const key = new THREE.DirectionalLight(0xffe9d4, 1.6); key.position.set(2, 3, 4);
  const rim = new THREE.DirectionalLight(0xb85a2c, 0.85); rim.position.set(-3, -1, 2);
  scene.add(key, rim, new THREE.AmbientLight(0xf4efe6, 0.5));

  const knot = new THREE.Mesh(
    new THREE.TorusKnotGeometry(0.9, 0.28, 240, 36, 2, 3),
    new THREE.MeshPhysicalMaterial({
      color: 0xffffff, metalness: 0.15, roughness: 0.08,
      clearcoat: 1.0, clearcoatRoughness: 0.15,
      iridescence: 0.95, iridescenceIOR: 1.45,
      iridescenceThicknessRange: [100, 800],
      sheen: 0.5, sheenColor: 0xe8a87c, sheenRoughness: 0.3,
      opacity: 0.92, transparent: true, side: THREE.DoubleSide,
    })
  );
  scene.add(knot);

  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.35, 1),
    new THREE.MeshPhysicalMaterial({
      color: 0xb85a2c, metalness: 0.95, roughness: 0.2,
      emissive: 0xb85a2c, emissiveIntensity: 0.2,
    })
  );
  scene.add(core);

  // Particles
  function makeParticles(count, r1, r2, color, size, opacity) {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = r1 + Math.random() * (r2 - r1);
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
    }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return new THREE.Points(g, new THREE.PointsMaterial({
      color, size, sizeAttenuation: true, transparent: true, opacity, depthWrite: false,
    }));
  }
  scene.add(makeParticles(120, 1.9, 3.9, 0xb85a2c, 0.022, 0.5));
  const innerDust = makeParticles(80, 0.9, 1.6, 0xfff5e8, 0.014, 0.7);
  scene.add(innerDust);

  let tmx = 0, tmy = 0, mx = 0, my = 0;
  const mouseHandler = (e) => {
    tmx = (e.clientX / window.innerWidth - 0.5) * 0.5;
    tmy = (e.clientY / window.innerHeight - 0.5) * 0.4;
  };
  const orientHandler = (e) => {
    if (e.gamma == null || e.beta == null) return;
    tmx = Math.max(-1, Math.min(1, e.gamma / 45)) * 0.3;
    tmy = Math.max(-1, Math.min(1, (e.beta - 45) / 45)) * 0.25;
  };
  window.addEventListener('mousemove', mouseHandler);
  window.addEventListener('deviceorientation', orientHandler, { passive: true });

  let t = 0, running = true;
  function tick() {
    if (!running || !document.body.contains(canvas)) {
      window.removeEventListener('resize', resizeHandler);
      window.removeEventListener('mousemove', mouseHandler);
      window.removeEventListener('deviceorientation', orientHandler);
      renderer.dispose();
      return;
    }
    t += 0.005;
    knot.rotation.x = t * 0.45; knot.rotation.y = t * 0.65;
    knot.position.y = Math.sin(t * 1.5) * 0.08;
    core.rotation.x = -t * 0.8; core.rotation.y = t * 1.1;
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
}


// ════════════════════════════════════════════════════════════════
// CART
// ════════════════════════════════════════════════════════════════
const cartBtn      = document.getElementById('cart-btn');
const cartCount    = document.getElementById('cart-count');
const cartDrawer   = document.getElementById('cart-drawer');
const cartClose    = document.getElementById('cart-close');
const cartItemsEl  = document.getElementById('cart-items');
const cartEmpty    = document.getElementById('cart-empty');
const cartFooter   = document.getElementById('cart-footer');
const cartTotalAmt = document.getElementById('cart-total-amount');
const checkoutBtn  = document.getElementById('checkout-btn');
const wishlistCountEl = document.getElementById('wishlist-count');

function updateCartBadge() {
  if (state.cart.count > 0) {
    cartCount.textContent = Math.round(state.cart.count);
    cartCount.classList.add('show');
  } else {
    cartCount.classList.remove('show');
  }
  updateMainButton();
}

function updateWishlistBadge() {
  if (state.wishlist.size > 0) {
    wishlistCountEl.textContent = state.wishlist.size;
    wishlistCountEl.classList.add('show');
  } else {
    wishlistCountEl.classList.remove('show');
  }
}

function updateMainButton() {
  if (!tg?.MainButton) return;
  const sheetEl = document.getElementById('checkout-sheet');
  if (sheetEl?.classList.contains('open')) {
    tg.MainButton.setText('Buyurtmani tasdiqlash');
    tg.MainButton.show(); tg.MainButton.enable();
    return;
  }
  if (state.cart.count > 0) {
    tg.MainButton.setText(`Savat · ${fmtMoney(state.cart.total)}`);
    tg.MainButton.color = '#1B1714';
    tg.MainButton.textColor = '#FFFDFA';
    tg.MainButton.show(); tg.MainButton.enable();
  } else {
    tg.MainButton.hide();
  }
}

function renderCart() {
  cartItemsEl.innerHTML = '';
  if (state.cart.items.length === 0) {
    cartEmpty.classList.remove('hidden');
    cartFooter.hidden = true;
    return;
  }
  cartEmpty.classList.add('hidden');
  cartFooter.hidden = false;

  for (const item of state.cart.items) {
    const div = document.createElement('div');
    div.className = 'cart-item';
    div.innerHTML = `
      <div class="cart-item-img">
        ${item.photo ? `<img src="${item.photo}" alt="" loading="lazy" onerror="this.remove()"/>` : '✦'}
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
  cartTotalAmt.textContent = fmtMoney(state.cart.total);
}

cartItemsEl.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const id = parseInt(btn.dataset.id);
  const action = btn.dataset.action;
  const item = state.cart.items.find((i) => i.product_id === id);
  if (!item) return;
  let newQty = item.quantity + (action === 'inc' ? 1 : -1);
  haptic.light();
  try {
    await API.post('/api/cart/update', { product_id: id, quantity: newQty });
    await loadCart();
  } catch (err) { haptic.warning(); showToast('Xato yuz berdi'); }
});

function openCart() {
  haptic.light();
  cartDrawer.classList.add('open');
  cartDrawer.setAttribute('aria-hidden', 'false');
  if (tg?.BackButton) { tg.BackButton.show(); tg.BackButton.onClick(closeCart); }
}
function closeCart() {
  cartDrawer.classList.remove('open');
  cartDrawer.setAttribute('aria-hidden', 'true');
  updateBackButton();
}
cartBtn.addEventListener('click', openCart);
cartClose.addEventListener('click', closeCart);
document.querySelector('.cart-backdrop').addEventListener('click', closeCart);

async function loadCart() {
  try {
    const data = await API.get('/api/cart');
    state.cart = data;
    updateCartBadge();
    renderCart();
  } catch (err) { console.error('Cart load error:', err); }
}

async function loadWishlistIds() {
  try {
    const data = await API.get('/api/wishlist');
    state.wishlist = new Set(data.ids);
    updateWishlistBadge();
  } catch (err) { console.error('Wishlist error:', err); }
}


// ════════════════════════════════════════════════════════════════
// CHECKOUT (same as v3, simplified)
// ════════════════════════════════════════════════════════════════
const sheetEl       = document.getElementById('checkout-sheet');
const sheetClose    = document.getElementById('checkout-close');
const submitBtn     = document.getElementById('submit-order');
const fAddress      = document.getElementById('f-address');
const fPhone        = document.getElementById('f-phone');
const fNotes        = document.getElementById('f-notes');
const summaryCount  = document.getElementById('summary-count');
const summaryTotal  = document.getElementById('summary-total');
let selectedPayment = 'cash';

function openCheckout() {
  if (state.cart.items.length === 0) {
    haptic.warning(); showToast("Savatingiz bo'sh"); return;
  }
  haptic.medium();
  if (!fPhone.value && tgUser?.phone_number) fPhone.value = tgUser.phone_number;
  summaryCount.textContent = `${Math.round(state.cart.count)} ta`;
  summaryTotal.textContent = fmtMoney(state.cart.total);
  closeCart();
  sheetEl.classList.add('open');
  if (tg?.BackButton) { tg.BackButton.show(); tg.BackButton.onClick(closeCheckout); }
  updateMainButton();
}
function closeCheckout() {
  sheetEl.classList.remove('open');
  updateBackButton();
  updateMainButton();
}
checkoutBtn.addEventListener('click', openCheckout);
sheetClose.addEventListener('click', closeCheckout);
sheetEl.querySelector('.sheet-backdrop').addEventListener('click', closeCheckout);

sheetEl.querySelectorAll('.pay-card').forEach(card => {
  card.addEventListener('click', () => {
    haptic.light();
    sheetEl.querySelectorAll('.pay-card').forEach(c => c.classList.remove('active'));
    card.classList.add('active');
    selectedPayment = card.dataset.pay;
  });
});

async function submitOrder() {
  const address = fAddress.value.trim();
  const phone = fPhone.value.trim();
  const notes = fNotes.value.trim();
  fAddress.classList.remove('error'); fPhone.classList.remove('error');
  if (address.length < 5) { fAddress.classList.add('error'); fAddress.focus(); haptic.warning(); showToast('Manzilni to\'liq yozing'); return; }
  if (phone.length < 7) { fPhone.classList.add('error'); fPhone.focus(); haptic.warning(); showToast('Telefon raqamni kiriting'); return; }

  submitBtn.disabled = true;
  if (tg?.MainButton) tg.MainButton.showProgress(false);
  haptic.medium();

  try {
    const result = await API.post('/api/orders', { address, phone, payment_method: selectedPayment, notes });
    haptic.success();
    closeCheckout();
    document.getElementById('success-order-id').textContent = `#${result.order_id}`;
    document.getElementById('success-modal').classList.add('open');
    fAddress.value = ''; fNotes.value = '';
    await loadCart();
    if (tg?.MainButton) tg.MainButton.hide();
  } catch (err) {
    haptic.error();
    showToast(err.message || 'Buyurtma yaratilmadi');
  } finally {
    submitBtn.disabled = false;
    if (tg?.MainButton) tg.MainButton.hideProgress();
  }
}
submitBtn.addEventListener('click', submitOrder);
document.getElementById('success-close').addEventListener('click', () => {
  haptic.light();
  document.getElementById('success-modal').classList.remove('open');
  navigate('orders');
});

if (tg?.MainButton) {
  tg.MainButton.onClick(() => {
    if (sheetEl.classList.contains('open')) submitOrder();
    else if (cartDrawer.classList.contains('open')) openCheckout();
    else openCart();
  });
}


// ════════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════════
async function loadShopInfo() {
  try {
    const data = await API.get('/api/shop');
    state.shop = data;
    document.getElementById('brand-name').textContent = data.name || 'Lady Maryam';
    document.title = `${data.name || 'Lady Maryam'} — Atelier`;
  } catch (err) { console.warn(err); }
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadShopInfo();
  await loadWishlistIds();
  await loadCart();
  navigate('home', null, { fromHistory: true });
});
