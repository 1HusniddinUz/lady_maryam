/* ════════════════════════════════════════════════════════════════
   Lady Maryam Atelier — Bot
   Vanilla JS + AI + Persistent Storage
   ──────────────────────────────────────────────────────────────── */

// ═══ DATA ═══════════════════════════════════════════════════════
const CATEGORIES = [
  { id: 'koylak',   name: "Ko'ylaklar" },
  { id: 'bluzka',   name: 'Bluzkalar' },
  { id: 'shim',     name: 'Shimlar' },
  { id: 'yubka',    name: 'Yubkalar' },
  { id: 'kostyum',  name: 'Kostyumlar' },
  { id: 'aksesuar', name: 'Aksessuarlar' },
];

const BASE_PRODUCTS = {
  koylak: [
    { id: 'k1', name: "Yozgi gulli ko'ylak",    price: 450000, mark: '✦', desc: 'Yengil chitdan, yoz uchun ideal' },
    { id: 'k2', name: "Kechki uzun ko'ylak",    price: 850000, mark: '❋', desc: 'Maxsus tadbirlar uchun nafis' },
    { id: 'k3', name: "Klassik ish ko'ylagi",   price: 620000, mark: '✺', desc: 'Ofisda kiyish uchun rasmiy' },
    { id: 'k4', name: "Shifon uzun ko'ylak",    price: 720000, mark: '✷', desc: 'Yengil shifondan, mavsum hiti' },
  ],
  bluzka: [
    { id: 'b1', name: 'Oq atlas bluzka',        price: 320000, mark: '✦', desc: 'Klassik dizayn, universal' },
    { id: 'b2', name: 'Ipakli bluzka',          price: 480000, mark: '❋', desc: 'Tabiiy ipakdan, premium' },
    { id: 'b3', name: 'Naqshli bluzka',         price: 380000, mark: '✺', desc: 'Yorqin gul naqshlari bilan' },
  ],
  shim: [
    { id: 's1', name: "To'g'ri klassik shim",   price: 520000, mark: '✦', desc: 'Ofis va kundalik uchun' },
    { id: 's2', name: 'Slim jinsi',             price: 420000, mark: '❋', desc: 'Premium denim, qulay' },
    { id: 's3', name: 'Keng oyoqli palazzo',    price: 580000, mark: '✺', desc: '2026 trend uslubi' },
  ],
  yubka: [
    { id: 'y1', name: 'Plisirovka yubka',       price: 380000, mark: '✦', desc: 'Yengil va nafis' },
    { id: 'y2', name: 'Charm uzun yubka',       price: 650000, mark: '❋', desc: 'Tabiiy charmdan' },
    { id: 'y3', name: 'Karandash yubka',        price: 420000, mark: '✺', desc: 'Klassik shakl, ofisga' },
  ],
  kostyum: [
    { id: 'ks1', name: 'Ikki qismli kostyum',   price: 1250000, mark: '✦', desc: 'Pidjak va shim' },
    { id: 'ks2', name: 'Yubkali kostyum',       price: 1180000, mark: '❋', desc: 'Pidjak va yubka' },
  ],
  aksesuar: [
    { id: 'a1', name: 'Charm sumka',            price: 680000, mark: '✦', desc: 'Tabiiy charm, zamonaviy' },
    { id: 'a2', name: "Ipak ro'mol",            price: 220000, mark: '❋', desc: 'Yorqin naqshli' },
    { id: 'a3', name: "Marvarid sirg'a",        price: 180000, mark: '✺', desc: 'Tabiiy marvariddan' },
  ],
};

// ═══ STATE ══════════════════════════════════════════════════════
const state = {
  messages: [],
  cart: [],
  orders: [],
  wishlist: new Set(),
  orderStep: null,         // null | 'name' | 'phone' | 'address' | 'confirm'
  orderData: { name: '', phone: '', address: '' },
  loading: false,
};

// ═══ STORAGE ════════════════════════════════════════════════════
const storage = {
  async get(key) {
    try {
      const res = await window.storage.get(key, false);
      return res ? JSON.parse(res.value) : null;
    } catch { return null; }
  },
  async set(key, value) {
    try {
      await window.storage.set(key, JSON.stringify(value), false);
    } catch (e) { console.error('Storage error:', e); }
  },
};

// ═══ HELPERS ════════════════════════════════════════════════════
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const fmtMoney = (n) =>
  Math.round(n).toLocaleString('ru-RU').replace(/,/g, ' ') + " so'm";

const escHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c])
  );

const now = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
};

const uuid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

// ═══ TOAST ══════════════════════════════════════════════════════
const toastEl = $('#toast');
let toastTimer;
function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2400);
}

// ═══ AI (Anthropic API) ═════════════════════════════════════════
async function askAI(userMessage, context = '') {
  const systemPrompt = `Sen "Lady Maryam Atelier" — ayollar uchun premium kiyim ateliesining AI maslahatchisisan.
Vazifang: mijozlarga nafosat bilan, do'stona uslubda yordam berish. Uslub bo'yicha maslahatlar berish.
Faqat O'ZBEK tilida, qisqa va elegant javob ber (maksimal 2-3 jumla).
Mijozni "siz" deb murojaat qil. Tilingiz sokin va nafis bo'lsin — atelier ruhida.
${context ? `\nKontekst: ${context}` : ''}`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1000,
        system: systemPrompt,
        messages: [{ role: 'user', content: userMessage }],
      }),
    });
    const data = await response.json();
    const text = data.content
      .filter((b) => b.type === 'text')
      .map((b) => b.text)
      .join('\n');
    return text || "Kechirasiz, hozir javob bera olmadim.";
  } catch (e) {
    console.error('AI error:', e);
    return "Texnik nosozlik. Iltimos, qaytadan urinib ko'ring.";
  }
}

async function generateProducts(category) {
  const catName = CATEGORIES.find((c) => c.id === category)?.name || category;
  const prompt = `Ayollar atelieri uchun "${catName}" kategoriyasidan 3 ta nafis mahsulot taklif qil.
JAVOBNI faqat JSON formatda, qo'shimcha matnsiz:
[{"name":"mahsulot nomi","price":narx_son,"mark":"bitta belgi: ✦ ❋ ✺ ✷","desc":"qisqa tavsif 4-6 so'z"}]
Narxlar 200000-1500000 so'm. Nomlar elegant va atelier ruhida.`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1000,
        messages: [{ role: 'user', content: prompt }],
      }),
    });
    const data = await response.json();
    const text = data.content.find((b) => b.type === 'text')?.text || '';
    const match = text.replace(/```json|```/g, '').match(/\[[\s\S]*\]/);
    if (match) {
      const products = JSON.parse(match[0]);
      return products.map((p, i) => ({
        ...p,
        id: `ai_${category}_${Date.now()}_${i}`,
      }));
    }
    return [];
  } catch (e) {
    console.error('Generate error:', e);
    return [];
  }
}

// ═══ MENU ═══════════════════════════════════════════════════════
function mainMenuButtons() {
  return [
    { text: 'Kolleksiya',      action: 'catalog' },
    { text: 'Savatcham',       action: 'cart' },
    { text: 'Buyurtmalarim',   action: 'orders' },
    { text: 'Sevimlilar',      action: 'wishlist' },
    { text: 'Atelier haqida',  action: 'about' },
    { text: 'Yetkazib berish', action: 'delivery' },
  ];
}

// ═══ RENDER MESSAGES ════════════════════════════════════════════
const chatArea = $('#chat-area');

function renderBotMessage(msg) {
  const row = document.createElement('div');
  row.className = 'msg-row bot';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = '✦';
  row.appendChild(avatar);

  const content = document.createElement('div');
  content.className = 'msg-content';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble bot-bubble';
  bubble.innerHTML = `
    <div class="msg-sender">Lady Maryam</div>
    <div class="msg-text">${escHtml(msg.text)}</div>
    <div class="msg-time">${msg.time}</div>
  `;
  content.appendChild(bubble);

  if (msg.products && msg.products.length > 0) {
    const stack = document.createElement('div');
    stack.className = 'products-stack';
    msg.products.forEach((p) => stack.appendChild(makeProductCard(p)));
    content.appendChild(stack);
  }

  if (msg.buttons && msg.buttons.length > 0) {
    const keys = document.createElement('div');
    keys.className = 'inline-keys';
    msg.buttons.forEach((btn) => {
      const b = document.createElement('button');
      b.className = 'inline-key';
      b.textContent = btn.text;
      b.addEventListener('click', () => handleButtonClick(btn));
      keys.appendChild(b);
    });
    content.appendChild(keys);
  }

  row.appendChild(content);
  chatArea.appendChild(row);
  scrollToBottom();
}

function renderUserMessage(msg) {
  const row = document.createElement('div');
  row.className = 'msg-row user';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble user-bubble';
  bubble.innerHTML = `
    <div class="msg-text">${escHtml(msg.text)}</div>
    <div class="msg-time">${msg.time} <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></div>
  `;
  row.appendChild(bubble);
  chatArea.appendChild(row);
  scrollToBottom();
}

function renderTyping() {
  const row = document.createElement('div');
  row.className = 'msg-row bot';
  row.id = 'typing-indicator';
  row.innerHTML = `
    <div class="msg-avatar">✦</div>
    <div class="msg-bubble bot-bubble typing-bubble">
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>
  `;
  chatArea.appendChild(row);
  scrollToBottom();
}

function removeTyping() {
  const t = $('#typing-indicator');
  if (t) t.remove();
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  });
}

// ═══ PRODUCT CARD FACTORY ═══════════════════════════════════════
function makeProductCard(product) {
  const isWished = state.wishlist.has(product.id);
  const card = document.createElement('div');
  card.className = 'product-card-bot';
  card.innerHTML = `
    <div class="product-card-img">
      <span class="product-mark">${escHtml(product.mark || '✦')}</span>
      <button class="product-wish ${isWished ? 'active' : ''}" data-wish="${product.id}" aria-label="Sevimlilar">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="${isWished ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
      </button>
    </div>
    <div class="product-card-body">
      <div class="product-card-name">${escHtml(product.name)}</div>
      <div class="product-card-desc">${escHtml(product.desc || '')}</div>
      <div class="product-card-foot">
        <div class="product-card-price">${fmtMoney(product.price)}</div>
        <button class="product-card-add" data-add='${escHtml(JSON.stringify(product))}'>
          <span>Savatga</span>
        </button>
      </div>
    </div>
  `;

  // Wishlist toggle
  card.querySelector('[data-wish]').addEventListener('click', (e) => {
    e.preventDefault();
    toggleWishlist(product);
    // Re-render this card's wishlist state
    const btn = card.querySelector('[data-wish]');
    const isNow = state.wishlist.has(product.id);
    btn.classList.toggle('active', isNow);
    const svg = btn.querySelector('svg');
    svg.setAttribute('fill', isNow ? 'currentColor' : 'none');
  });

  // Add to cart
  card.querySelector('[data-add]').addEventListener('click', () => addToCart(product));

  return card;
}

// ═══ MESSAGE LOGIC ══════════════════════════════════════════════
function sendBotMessage(msg) {
  const full = { role: 'bot', time: now(), ...msg };
  state.messages.push(full);
  renderBotMessage(full);
  storage.set('chat_history', state.messages.slice(-50));
}

function sendUserMessage(text) {
  const full = { role: 'user', time: now(), text };
  state.messages.push(full);
  renderUserMessage(full);
  storage.set('chat_history', state.messages.slice(-50));
}

function restoreMessages() {
  chatArea.innerHTML = '';
  state.messages.forEach((msg) => {
    if (msg.role === 'bot') renderBotMessage(msg);
    else renderUserMessage(msg);
  });
}

// ═══ ACTIONS ════════════════════════════════════════════════════
async function handleAction(action, data) {
  state.loading = true;

  if (action === 'catalog') {
    sendBotMessage({
      text: 'Kolleksiyamiz — kategoriyani tanlang:',
      buttons: CATEGORIES
        .map((c) => ({ text: c.name, action: 'category', data: c.id }))
        .concat([{ text: '← Bosh sahifa', action: 'main' }]),
    });
  } else if (action === 'category') {
    const products = BASE_PRODUCTS[data] || [];
    const cat = CATEGORIES.find((c) => c.id === data);
    sendBotMessage({
      text: `${cat.name} — tanlangan asarlar:`,
      products,
      buttons: [
        { text: '✦ AI tavsiyalari', action: 'ai_recommend', data },
        { text: '← Kolleksiya', action: 'catalog' },
      ],
    });
  } else if (action === 'ai_recommend') {
    sendBotMessage({ text: 'AI siz uchun maxsus tanlov tayyorlamoqda…' });
    renderTyping();
    const products = await generateProducts(data);
    removeTyping();
    if (products.length > 0) {
      sendBotMessage({
        text: 'Mana siz uchun tanlangan asarlar:',
        products,
        buttons: [
          { text: '← Kolleksiya', action: 'catalog' },
          { text: '← Bosh sahifa', action: 'main' },
        ],
      });
    } else {
      sendBotMessage({
        text: 'Kechirasiz, hozir taklif tayyorlay olmadim.',
        buttons: [{ text: '← Kolleksiya', action: 'catalog' }],
      });
    }
  } else if (action === 'cart') {
    openModal('cart');
  } else if (action === 'orders') {
    openModal('orders');
  } else if (action === 'wishlist') {
    openModal('wishlist');
  } else if (action === 'about') {
    sendBotMessage({
      text: "Lady Maryam Atelier — 2020-yildan beri Toshkentda ayollar uchun premium kiyim yaratamiz.\n\n«Liboslar shunchaki kiyim emas — ular hikoya, his va xotira.»\n\n— Sof tikuv\n— Tabiiy matolar\n— 5000+ mamnun mijoz\n— Cheklanmagan e'tibor\n\nManzil — Toshkent, Chilonzor, Bunyodkor 12\nAloqa — +998 90 123 45 67",
      buttons: [{ text: '← Bosh sahifa', action: 'main' }],
    });
  } else if (action === 'delivery') {
    sendBotMessage({
      text: "Yetkazib berish:\n\n— Toshkent shahri bo'ylab BEPUL (500 000 so'mdan yuqori)\n— Toshkent ichida — 30 000 so'm\n— Viloyatlarga — 50 000 so'mdan\n\nMuddat — 1–2 kun (Toshkent), 2–5 kun (viloyatlar)\n\nTo'lov — Naqd, Click, Payme, Uzcard",
      buttons: [{ text: '← Bosh sahifa', action: 'main' }],
    });
  } else if (action === 'main') {
    sendBotMessage({
      text: 'Bosh sahifa. Quyidan tanlang:',
      buttons: mainMenuButtons(),
    });
  } else if (action === 'start_order') {
    closeModal('cart');
    state.orderStep = 'name';
    sendBotMessage({
      text: 'Buyurtmani rasmiylashtirish.\n\nIsmingizni yozing:',
    });
  } else if (action === 'confirm_order') {
    await confirmOrder();
  } else if (action === 'cancel_order') {
    cancelOrder();
  }

  state.loading = false;
}

async function handleButtonClick(btn) {
  sendUserMessage(btn.text);
  await handleAction(btn.action, btn.data);
}

// ═══ CART ═══════════════════════════════════════════════════════
function addToCart(product) {
  const existing = state.cart.find((p) => p.id === product.id);
  if (existing) {
    existing.qty += 1;
  } else {
    state.cart.push({ ...product, qty: 1 });
  }
  storage.set('cart', state.cart);
  updateCartBadge();
  renderCart();
  showToast(`«${product.name}» savatga qo'shildi`);
  sendBotMessage({
    text: `«${product.name}» savatga qo'shildi.`,
    buttons: [
      { text: "Savatchani ko'rish", action: 'cart' },
      { text: 'Davom etish',        action: 'catalog' },
    ],
  });
}

function removeFromCart(id) {
  state.cart = state.cart.filter((p) => p.id !== id);
  storage.set('cart', state.cart);
  updateCartBadge();
  renderCart();
}

function updateQty(id, delta) {
  state.cart = state.cart
    .map((p) => (p.id === id ? { ...p, qty: p.qty + delta } : p))
    .filter((p) => p.qty > 0);
  storage.set('cart', state.cart);
  updateCartBadge();
  renderCart();
}

const cartTotal = () => state.cart.reduce((s, p) => s + p.price * p.qty, 0);
const cartCount = () => state.cart.reduce((s, p) => s + p.qty, 0);

function updateCartBadge() {
  const badge = $('#cart-badge');
  const count = cartCount();
  if (count > 0) {
    badge.textContent = count;
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }
}

function updateWishlistBadge() {
  const badge = $('#wishlist-badge');
  if (state.wishlist.size > 0) {
    badge.textContent = state.wishlist.size;
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }
}

function renderCart() {
  const body = $('#cart-body');
  const foot = $('#cart-foot');
  body.innerHTML = '';

  if (state.cart.length === 0) {
    body.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">∅</div>
        <h3 class="empty-title">Savatchangiz bo'sh</h3>
        <p class="empty-text">Mahsulot tanlash uchun kolleksiyamizga tashrif buyuring.</p>
      </div>
    `;
    foot.hidden = true;
    return;
  }

  state.cart.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'cart-item';
    row.innerHTML = `
      <div class="cart-item-img">${escHtml(item.mark || '✦')}</div>
      <div class="cart-item-info">
        <div class="cart-item-name">${escHtml(item.name)}</div>
        <div class="cart-item-meta">${fmtMoney(item.price)}</div>
      </div>
      <div class="cart-item-ctl">
        <div class="cart-qty-ctl">
          <button class="cart-qty-btn" data-dec="${item.id}">−</button>
          <span class="cart-qty-num">${item.qty}</span>
          <button class="cart-qty-btn" data-inc="${item.id}">+</button>
        </div>
        <button class="cart-item-del" data-del="${item.id}" aria-label="O'chirish">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
          </svg>
        </button>
      </div>
    `;
    body.appendChild(row);
  });

  $('#cart-total').textContent = fmtMoney(cartTotal());
  foot.hidden = false;

  // Wire up controls
  body.querySelectorAll('[data-dec]').forEach((b) =>
    b.addEventListener('click', () => updateQty(b.dataset.dec, -1))
  );
  body.querySelectorAll('[data-inc]').forEach((b) =>
    b.addEventListener('click', () => updateQty(b.dataset.inc, +1))
  );
  body.querySelectorAll('[data-del]').forEach((b) =>
    b.addEventListener('click', () => removeFromCart(b.dataset.del))
  );
}

// ═══ ORDERS ═════════════════════════════════════════════════════
function renderOrders() {
  const body = $('#orders-body');
  body.innerHTML = '';

  if (state.orders.length === 0) {
    body.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">∅</div>
        <h3 class="empty-title">Hali buyurtma yo'q</h3>
        <p class="empty-text">Birinchi buyurtmangizdan keyin bu yerda ko'rinadi.</p>
      </div>
    `;
    return;
  }

  state.orders.forEach((order) => {
    const card = document.createElement('div');
    card.className = 'order-card';
    const itemsHtml = order.items
      .map(
        (it) => `
        <div class="order-items-row">
          <span>${escHtml(it.mark || '✦')} ${escHtml(it.name)} × ${it.qty}</span>
          <span class="price">${fmtMoney(it.price * it.qty)}</span>
        </div>`
      )
      .join('');
    card.innerHTML = `
      <div class="order-head">
        <div>
          <div class="order-id">${escHtml(order.id)}</div>
          <div class="order-date">${escHtml(order.date)}</div>
        </div>
        <span class="status-pill">${escHtml(order.status)}</span>
      </div>
      <div class="order-items">${itemsHtml}</div>
      <div class="order-foot">
        <span class="order-meta">${order.items.length} ta mahsulot</span>
        <span class="order-total">${fmtMoney(order.total)}</span>
      </div>
    `;
    body.appendChild(card);
  });
}

async function confirmOrder() {
  const num = `LM-${Date.now().toString().slice(-6)}`;
  state.orders.unshift({
    id: num,
    date: new Date().toLocaleString('uz-UZ'),
    items: [...state.cart],
    total: cartTotal(),
    customer: { ...state.orderData },
    status: 'yangi',
  });
  await storage.set('orders', state.orders);

  const total = cartTotal();
  state.cart = [];
  await storage.set('cart', state.cart);
  updateCartBadge();
  renderCart();

  state.orderStep = null;
  renderOrders();

  sendBotMessage({
    text: `Buyurtmangiz qabul qilindi.\n\nRaqam — ${num}\nJami — ${fmtMoney(total)}\n\nTez orada operator siz bilan bog'lanadi.\n\nTashrifingiz uchun rahmat.`,
    buttons: [
      { text: 'Buyurtmalarim', action: 'orders' },
      { text: '← Bosh sahifa', action: 'main' },
    ],
  });
}

function cancelOrder() {
  state.orderStep = null;
  sendBotMessage({
    text: 'Buyurtma bekor qilindi.',
    buttons: mainMenuButtons(),
  });
}

// ═══ WISHLIST ═══════════════════════════════════════════════════
function toggleWishlist(product) {
  if (state.wishlist.has(product.id)) {
    state.wishlist.delete(product.id);
  } else {
    state.wishlist.add(product.id);
  }
  storage.set('wishlist', Array.from(state.wishlist));
  updateWishlistBadge();
  renderWishlist();
}

function renderWishlist() {
  const body = $('#wishlist-body');
  body.innerHTML = '';

  const allProducts = Object.values(BASE_PRODUCTS).flat();
  const wishlistProducts = allProducts.filter((p) => state.wishlist.has(p.id));

  if (wishlistProducts.length === 0) {
    body.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">♡</div>
        <h3 class="empty-title">Hali bo'sh</h3>
        <p class="empty-text">Mahsulot ustidagi ♥ ni bosing — bu yerda saqlanadi.</p>
      </div>
    `;
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'wish-grid';

  wishlistProducts.forEach((p) => {
    const card = document.createElement('div');
    card.className = 'wish-card';
    card.innerHTML = `
      <div class="wish-img">
        <span class="wish-mark">${escHtml(p.mark || '✦')}</span>
        <button class="product-wish active" data-unwish="${p.id}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
        </button>
      </div>
      <div class="wish-info">
        <div class="wish-name">${escHtml(p.name)}</div>
        <div class="wish-price">${fmtMoney(p.price)}</div>
      </div>
    `;
    card.querySelector('[data-unwish]').addEventListener('click', () => toggleWishlist(p));
    grid.appendChild(card);
  });

  body.appendChild(grid);
}

// ═══ MODAL CONTROLS ═════════════════════════════════════════════
function openModal(name) {
  const el = $(`#modal-${name}`);
  el.hidden = false;
  // Re-render contents
  if (name === 'cart') renderCart();
  else if (name === 'orders') renderOrders();
  else if (name === 'wishlist') renderWishlist();
}

function closeModal(name) {
  const el = $(`#modal-${name}`);
  el.hidden = true;
}

// ═══ INPUT HANDLING ═════════════════════════════════════════════
const inputField = $('#input-field');
const btnSend = $('#btn-send');

async function handleSend() {
  const text = inputField.value.trim();
  if (!text || state.loading) return;

  inputField.value = '';
  sendUserMessage(text);
  state.loading = true;
  btnSend.disabled = true;

  // Order flow
  if (state.orderStep === 'name') {
    state.orderData.name = text;
    state.orderStep = 'phone';
    sendBotMessage({ text: `Rahmat, ${text}.\n\nTelefon raqamingizni yozing (masalan, +998901234567):` });
    state.loading = false; btnSend.disabled = false; return;
  }
  if (state.orderStep === 'phone') {
    state.orderData.phone = text;
    state.orderStep = 'address';
    sendBotMessage({ text: "Yetkazib berish manzilini to'liq yozing:" });
    state.loading = false; btnSend.disabled = false; return;
  }
  if (state.orderStep === 'address') {
    state.orderData.address = text;
    await storage.set('user_info', state.orderData);
    state.orderStep = 'confirm';

    const summary = state.cart
      .map((p) => `— ${p.name} × ${p.qty} = ${fmtMoney(p.price * p.qty)}`)
      .join('\n');

    sendBotMessage({
      text: `Tasdiqlang:\n\nIsm — ${state.orderData.name}\nTel — ${state.orderData.phone}\nManzil — ${state.orderData.address}\n\n${summary}\n\nJami — ${fmtMoney(cartTotal())}`,
      buttons: [
        { text: '✓ Tasdiqlash',    action: 'confirm_order' },
        { text: '✕ Bekor qilish',  action: 'cancel_order' },
      ],
    });
    state.loading = false; btnSend.disabled = false; return;
  }

  // Quick keyword matches
  const lower = text.toLowerCase();
  if (lower.includes('katalog') || lower.includes('kolleksiya') || lower.includes('mahsulot')) {
    await handleAction('catalog');
    state.loading = false; btnSend.disabled = false; return;
  }
  if (lower.includes('savat')) {
    openModal('cart');
    state.loading = false; btnSend.disabled = false; return;
  }
  if (lower.includes('buyurtma')) {
    openModal('orders');
    state.loading = false; btnSend.disabled = false; return;
  }
  if (lower.includes('sevim')) {
    openModal('wishlist');
    state.loading = false; btnSend.disabled = false; return;
  }

  // Otherwise — ask AI
  renderTyping();
  const context = state.cart.length > 0
    ? `Mijoz savatchasida ${state.cart.length} ta mahsulot bor.`
    : '';
  const aiResponse = await askAI(text, context);
  removeTyping();
  sendBotMessage({
    text: aiResponse,
    buttons: [
      { text: 'Kolleksiya',     action: 'catalog' },
      { text: '← Bosh sahifa',  action: 'main' },
    ],
  });
  state.loading = false; btnSend.disabled = false;
}

// ═══ CLEAR CHAT ═════════════════════════════════════════════════
async function clearChat() {
  if (!confirm('Suhbatni tozalashni xohlaysizmi?')) return;
  state.messages = [];
  await storage.set('chat_history', []);
  chatArea.innerHTML = '';
  sendBotMessage({
    text: "Assalomu alaykum.\n\nLady Maryam Atelier'ga xush kelibsiz.",
    buttons: mainMenuButtons(),
  });
}

// ═══ EVENT LISTENERS ════════════════════════════════════════════
btnSend.addEventListener('click', handleSend);
inputField.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleSend();
});

$('#btn-cart').addEventListener('click', () => openModal('cart'));
$('#btn-orders')?.addEventListener('click', () => openModal('orders'));
$('#btn-wishlist').addEventListener('click', () => openModal('wishlist'));
$('#btn-clear').addEventListener('click', clearChat);
$('#btn-checkout').addEventListener('click', () => handleAction('start_order'));

// Modal close buttons + backdrops
$$('[data-close]').forEach((el) => {
  el.addEventListener('click', () => closeModal(el.dataset.close));
});

// ═══ INIT ═══════════════════════════════════════════════════════
async function init() {
  // Restore state from storage
  const savedMessages = await storage.get('chat_history');
  const savedCart     = await storage.get('cart');
  const savedOrders   = await storage.get('orders');
  const savedWish     = await storage.get('wishlist');
  const savedUser     = await storage.get('user_info');

  if (savedCart)   state.cart = savedCart;
  if (savedOrders) state.orders = savedOrders;
  if (savedWish)   state.wishlist = new Set(savedWish);
  if (savedUser)   state.orderData = savedUser;

  updateCartBadge();
  updateWishlistBadge();

  if (savedMessages && savedMessages.length > 0) {
    state.messages = savedMessages;
    restoreMessages();
  } else {
    sendBotMessage({
      text: "Assalomu alaykum.\n\nLady Maryam Atelier'ga xush kelibsiz — har bir libosda nafosat va e'tibor.\n\nQuyidan tanlang yoki menga to'g'ridan-to'g'ri savol bering.",
      buttons: mainMenuButtons(),
    });
  }
}

document.addEventListener('DOMContentLoaded', init);
