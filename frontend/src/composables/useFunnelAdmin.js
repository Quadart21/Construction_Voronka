import { computed, onMounted, reactive, ref } from "vue";
import { getApiBase } from "../utils/apiBase";

export const tabGroups = [
  {
    title: "Сайт и лиды",
    hint: "Заявки с главной страницы",
    items: [
      {
        key: "leads",
        label: "Заявки с лендинга",
        description: "Без регистрации; дублируем в Telegram администраторам"
      }
    ]
  },
  {
    title: "Картина по воронке",
    hint: "Цифры и узкие места без настройки бота",
    items: [
      { key: "dashboard", label: "Главная", description: "Сколько людей, сколько оплат, общая конверсия" },
      { key: "conversions", label: "Где останавливаются", description: "На каком шаге чаще всего пропадают люди" },
      { key: "accounting", label: "Оплаты", description: "Выручка, счета и последние платежи" }
    ]
  },
  {
    title: "Как работает бот",
    hint: "Сообщения, порядок и напоминания",
    items: [
      { key: "steps", label: "Сообщения шагов", description: "Тексты, картинки и видео в цепочке" },
      { key: "chain", label: "Порядок и кнопки", description: "Последовательность шагов и развилки" },
      { key: "automations", label: "Автонапоминания", description: "Сообщения, если человек пропал" }
    ]
  },
  {
    title: "Люди и справочники",
    hint: "Кто подписался и что делал",
    items: [
      { key: "users", label: "Подписчики", description: "Кто в воронке и на каком шаге" },
      { key: "events", label: "История", description: "Что люди нажимали и когда платили" },
      { key: "settings", label: "Настройки бота", description: "Приветствие, цена, материал после оплаты" }
    ]
  },
  {
    title: "Администрирование",
    hint: "Доступ к панели",
    items: [{ key: "admins", label: "Администраторы", description: "Новые входы: при первом входе обязательна 2FA" }]
  }
];

export const tabMeta = Object.fromEntries(tabGroups.flatMap((group) => group.items.map((item) => [item.key, item])));

const TOKEN_STORAGE = "funnel_admin_access_token";

export function useFunnelAdmin() {
  const apiBase = computed(() => getApiBase());
  const loginForm = reactive({ username: "", password: "" });
  const isAuthenticated = ref(false);
  const accessToken = ref(typeof localStorage !== "undefined" ? localStorage.getItem(TOKEN_STORAGE) || "" : "");
  const sessionUser = ref(null);
  const authPhase = ref("password");
  const partialToken = ref("");
  const setup2faToken = ref("");
  const setup2faProvisioningUri = ref("");
  const setup2faSecret = ref("");
  const totpCode = ref("");
  const userSearch = ref("");
  const eventSearch = ref("");
  const adminsList = ref([]);
  const newAdminForm = reactive({ username: "", password: "" });

  const state = reactive({
    dashboard: null,
    conversions: null,
    accounting: null,
    funnelSteps: [],
    funnelBranches: [],
    automations: [],
    users: [],
    events: [],
    settings: { funnel_copy: {}, offer: { delivery: { buttons: [] } }, diagram_layout: {} },
    leads: [],
    loading: false,
    error: "",
    success: "",
    activeTab: "dashboard"
  });

  const chainBranchSourceCode = ref("");
  const branchTypeRef = ref("internal");

  const stepDraft = reactive({
    id: null,
    code: "",
    title: "",
    body: "",
    step_type: "content",
    media_type: "",
    media_url: "",
    media_caption: "",
    segment_key: "",
    cta_text: "",
    next_step_code: "",
    trigger_keywords: "",
    sort_order: 0,
    is_active: true
  });

  const branchDraft = reactive({
    id: null,
    source_step_code: "",
    button_text: "",
    target_step_code: "",
    url: "",
    sort_order: 1,
    is_active: true
  });

  const automationDraft = reactive({
    id: null,
    code: "",
    trigger_type: "inactivity",
    trigger_step: "",
    inactivity_hours: 2,
    title: "",
    body: "",
    bonus_label: "",
    target_step_code: "",
    is_active: true
  });

  function authHeaders() {
    const h = { "Content-Type": "application/json" };
    if (accessToken.value) h.Authorization = `Bearer ${accessToken.value}`;
    return h;
  }

  function authOnlyHeaders() {
    const h = {};
    if (accessToken.value) h.Authorization = `Bearer ${accessToken.value}`;
    return h;
  }

  function clearSession() {
    accessToken.value = "";
    if (typeof localStorage !== "undefined") localStorage.removeItem(TOKEN_STORAGE);
    sessionUser.value = null;
    isAuthenticated.value = false;
    authPhase.value = "password";
    partialToken.value = "";
    setup2faToken.value = "";
    setup2faProvisioningUri.value = "";
    setup2faSecret.value = "";
    totpCode.value = "";
  }

  function applyAccessToken(token) {
    accessToken.value = token;
    if (typeof localStorage !== "undefined") localStorage.setItem(TOKEN_STORAGE, token);
    isAuthenticated.value = true;
    authPhase.value = "password";
    partialToken.value = "";
    setup2faToken.value = "";
    setup2faProvisioningUri.value = "";
    setup2faSecret.value = "";
    totpCode.value = "";
    loginForm.password = "";
  }

  const setup2faQrUrl = computed(() => {
    const uri = setup2faProvisioningUri.value;
    if (!uri) return "";
    return `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(uri)}`;
  });

  function ensureSettingsShape() {
    if (!state.settings.funnel_copy) state.settings.funnel_copy = {};
    if (!state.settings.offer) state.settings.offer = {};
    if (!state.settings.offer.delivery) state.settings.offer.delivery = {};
    if (!Array.isArray(state.settings.offer.delivery.buttons)) state.settings.offer.delivery.buttons = [];
  }

  function normalizeNullable(payload) {
    return Object.fromEntries(
      Object.entries(payload)
        .filter(([key]) => key !== "id")
        .map(([key, value]) => [key, value === "" ? null : value])
    );
  }

  const orderedSteps = computed(() => [...state.funnelSteps].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0)));
  const nextSortOrder = computed(() => (orderedSteps.value.at(-1)?.sort_order || 0) + 1);

  function resetStepDraft() {
    Object.assign(stepDraft, {
      id: null,
      code: "",
      title: "",
      body: "",
      step_type: "content",
      media_type: "",
      media_url: "",
      media_caption: "",
      segment_key: "",
      cta_text: "",
      next_step_code: "",
      trigger_keywords: "",
      sort_order: nextSortOrder.value,
      is_active: true
    });
    resetBranchDraft();
  }

  function resetBranchDraftForSource(sourceStepCode = "") {
    Object.assign(branchDraft, {
      id: null,
      source_step_code: sourceStepCode,
      button_text: "",
      target_step_code: "",
      url: "",
      sort_order: branchesForStep(sourceStepCode).length + 1,
      is_active: true
    });
    branchTypeRef.value = "internal";
  }

  function resetBranchDraft() {
    resetBranchDraftForSource(stepDraft.code || "");
  }

  function resetAutomationDraft() {
    Object.assign(automationDraft, {
      id: null,
      code: "",
      trigger_type: "inactivity",
      trigger_step: "",
      inactivity_hours: 2,
      title: "",
      body: "",
      bonus_label: "",
      target_step_code: "",
      is_active: true
    });
  }

  function stepTypeLabel(type) {
    return (
      {
        segment_entry: "Старт",
        content: "Польза",
        offer: "Предложение",
        payment: "Оплата"
      }[type] || "Шаг"
    );
  }

  function mediaTypeLabel(type) {
    return (
      {
        photo: "Фото",
        video: "Видео",
        animation: "GIF / анимация",
        gif: "GIF / анимация",
        document: "Файл"
      }[type] || "Медиа"
    );
  }

  function generateCode(text, fallback) {
    const normalized = (text || fallback || "step")
      .toLowerCase()
      .replace(/[^a-z0-9а-яё\s_-]/gi, "")
      .trim()
      .replace(/\s+/g, "_");
    return normalized || fallback;
  }

  function detectMediaType(file) {
    const type = file?.type || "";
    const name = (file?.name || "").toLowerCase();
    if (type === "image/gif" || name.endsWith(".gif")) return "animation";
    if (type.startsWith("image/")) return "photo";
    if (type.startsWith("video/")) return "video";
    return "document";
  }

  function apiRoot() {
    const base = apiBase.value;
    if (base.startsWith("http://") || base.startsWith("https://")) {
      return base.replace(/\/api\/?$/, "").replace(/\/$/, "");
    }
    return "";
  }

  function mediaPreviewUrl(mediaUrl) {
    const value = (mediaUrl || "").trim();
    if (!value) return "";
    if (value.startsWith("upload://")) {
      return `${apiRoot()}/uploads/${encodeURIComponent(value.slice("upload://".length))}`;
    }
    if (value.startsWith("/uploads/")) {
      return `${apiRoot()}${value}`;
    }
    return value;
  }

  function isImagePreview(target) {
    const type = target?.media_type || "";
    const url = (target?.media_url || "").toLowerCase();
    return type === "photo" || type === "gif" || Boolean(url.match(/\.(png|jpe?g|webp|gif)(\?.*)?$/));
  }

  function isVideoPreview(target) {
    const type = target?.media_type || "";
    const url = (target?.media_url || "").toLowerCase();
    return type === "video" || (type === "animation" && !url.endsWith(".gif")) || Boolean(url.match(/\.(mp4|webm|mov)(\?.*)?$/));
  }

  function transitionLabel() {
    return "Основной переход";
  }

  function buttonsLabel(step) {
    return `Доп. кнопок: ${branchesForStep(step.code).length}`;
  }

  function tabLabel(tab) {
    return tabMeta[tab]?.label || tab;
  }

  async function request(path, options = {}) {
    const p = path.startsWith("/") ? path : `/${path}`;
    const url = `${apiBase.value}${p}`;
    const hadToken = Boolean(accessToken.value);
    const response = await fetch(url, {
      ...options,
      headers: { ...authHeaders(), ...(options.headers || {}) }
    });
    if (!response.ok) {
      let msg = `Ошибка сервера (${response.status})`;
      try {
        const j = await response.json();
        if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      } catch (_) {
        /* ignore */
      }
      if (response.status === 401 && hadToken) clearSession();
      throw new Error(msg);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  async function uploadAdminFile(event, target, field = "media_url") {
    const file = event.target.files?.[0];
    if (!file) return;
    const detectedType = detectMediaType(file);
    state.error = "";
    state.success = "";
    state.loading = true;
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${apiBase.value}/uploads`, {
        method: "POST",
        headers: authOnlyHeaders(),
        body: form
      });
      if (!response.ok) throw new Error(`Не удалось загрузить файл (${response.status})`);
      const result = await response.json();
      target[field] = result.media_url;
      if ("media_type" in target && !target.media_type) target.media_type = detectedType;
      state.success = "Файл прикреплён.";
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
      event.target.value = "";
    }
  }

  async function loadAll() {
    state.loading = true;
    state.error = "";
    try {
      const [dashboard, conversions, accounting, funnelSteps, funnelBranches, automations, users, events, settings, leads] =
        await Promise.all([
          request("/dashboard"),
          request("/conversions"),
          request("/accounting"),
          request("/funnel-steps"),
          request("/funnel-branches"),
          request("/automations"),
          request("/users"),
          request("/events"),
          request("/settings"),
          request("/leads")
        ]);
      Object.assign(state, {
        dashboard,
        conversions,
        accounting,
        funnelSteps,
        funnelBranches,
        automations,
        users,
        events,
        settings,
        leads
      });
      ensureSettingsShape();
      if (!stepDraft.id && !stepDraft.code) stepDraft.sort_order = nextSortOrder.value;
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
    }
  }

  function editStep(step) {
    Object.assign(stepDraft, { ...step });
    resetBranchDraft();
    state.success = "";
    state.activeTab = "steps";
  }

  function createStepAfter(step) {
    resetStepDraft();
    stepDraft.sort_order = (step.sort_order || 0) + 1;
    state.activeTab = "steps";
  }

  function editBranch(branch, targetTab = state.activeTab) {
    Object.assign(branchDraft, { ...branch, url: branch.url || "" });
    branchTypeRef.value = branch.url ? "external" : "internal";
    chainBranchSourceCode.value = targetTab === "chain" ? branch.source_step_code : "";
    state.activeTab = targetTab;
  }

  function editAutomation(item) {
    Object.assign(automationDraft, { ...item });
    state.success = "";
    state.activeTab = "automations";
  }

  async function saveStep() {
    state.error = "";
    state.success = "";
    if (!stepDraft.code) stepDraft.code = generateCode(stepDraft.title, `step_${Date.now()}`);
    const payload = JSON.stringify(normalizeNullable(stepDraft));
    if (stepDraft.id) {
      await request(`/funnel-steps/${stepDraft.id}`, { method: "PUT", body: payload });
      state.success = "Сохранено. Изменения уже в боте.";
    } else {
      await request("/funnel-steps", { method: "POST", body: payload });
      state.success = "Шаг добавлен.";
    }
    await loadAll();
    editStep(state.funnelSteps.find((item) => item.code === stepDraft.code) || state.funnelSteps.at(-1) || stepDraft);
  }

  async function saveBranch(sourceStepCode = null) {
    state.error = "";
    state.success = "";
    if (sourceStepCode && typeof sourceStepCode !== "string") sourceStepCode = null;
    const sourceCode = sourceStepCode || branchDraft.source_step_code || stepDraft.code;
    if (!sourceCode || !branchDraft.button_text) {
      state.error = "Укажите шаг и текст на кнопке.";
      return;
    }
    if (branchTypeRef.value === "internal" && !branchDraft.target_step_code) {
      state.error = "Выберите шаг, куда ведёт кнопка.";
      return;
    }
    if (branchTypeRef.value === "external" && !branchDraft.url) {
      state.error = "Вставьте ссылку (начинается с https://).";
      return;
    }
    branchDraft.source_step_code = sourceCode;
    if (branchTypeRef.value === "external") branchDraft.target_step_code = "";
    else branchDraft.url = "";
    const payload = JSON.stringify(normalizeNullable(branchDraft));
    if (branchDraft.id) {
      await request(`/funnel-branches/${branchDraft.id}`, { method: "PUT", body: payload });
      state.success = "Кнопка обновлена.";
    } else {
      await request("/funnel-branches", { method: "POST", body: payload });
      state.success = "Кнопка добавлена.";
    }
    await loadAll();
    if (state.activeTab === "chain") {
      chainBranchSourceCode.value = "";
      resetBranchDraftForSource("");
    } else {
      resetBranchDraft();
    }
  }

  async function deleteBranch(branchId) {
    state.error = "";
    state.success = "";
    await request(`/funnel-branches/${branchId}`, { method: "DELETE" });
    state.success = "Кнопка удалена.";
    await loadAll();
  }

  async function deleteStep(step) {
    if (!confirm(`Удалить шаг «${step.title}»? Все кнопки этого шага тоже удалятся.`)) return;
    state.error = "";
    state.success = "";
    await request(`/funnel-steps/${step.id}`, { method: "DELETE" });
    state.success = "Шаг удалён.";
    if (stepDraft.id === step.id) resetStepDraft();
    await loadAll();
  }

  async function deleteAllSteps() {
    if (!confirm("Удалить всю цепочку? Отменить будет нельзя.")) return;
    state.error = "";
    state.success = "";
    await request("/funnel-steps", { method: "DELETE" });
    state.success = "Цепочка очищена.";
    resetStepDraft();
    await loadAll();
  }

  async function saveAutomation() {
    state.error = "";
    state.success = "";
    if (!automationDraft.code) automationDraft.code = generateCode(automationDraft.title, `auto_${Date.now()}`);
    const payload = JSON.stringify(normalizeNullable(automationDraft));
    if (automationDraft.id) {
      await request(`/automations/${automationDraft.id}`, { method: "PUT", body: payload });
      state.success = "Напоминание обновлено.";
    } else {
      await request("/automations", { method: "POST", body: payload });
      state.success = "Напоминание добавлено.";
    }
    resetAutomationDraft();
    await loadAll();
  }

  async function saveSetting(key) {
    state.error = "";
    state.success = "";
    ensureSettingsShape();
    await request(`/settings/${key}`, { method: "PUT", body: JSON.stringify(state.settings[key]) });
    state.success = "Сохранено.";
    await loadAll();
  }

  function addDeliveryButton() {
    ensureSettingsShape();
    state.settings.offer.delivery.buttons.push({ text: "", url: "" });
  }

  function removeDeliveryButton(index) {
    ensureSettingsShape();
    state.settings.offer.delivery.buttons.splice(index, 1);
  }

  async function saveStepOrder(ordered, message = "Порядок обновлён.") {
    state.error = "";
    state.success = "";
    await Promise.all(
      ordered.map((step, index) =>
        request(`/funnel-steps/${step.id}`, {
          method: "PUT",
          body: JSON.stringify(normalizeNullable({ ...step, sort_order: index + 1 }))
        })
      )
    );
    state.success = message;
    await loadAll();
  }

  async function moveStep(step, offset) {
    const ordered = [...orderedSteps.value];
    const currentIndex = ordered.findIndex((item) => item.id === step.id);
    const nextIndex = currentIndex + offset;
    if (currentIndex === -1 || nextIndex < 0 || nextIndex >= ordered.length) return;
    [ordered[currentIndex], ordered[nextIndex]] = [ordered[nextIndex], ordered[currentIndex]];
    await saveStepOrder(ordered);
  }

  async function updateStepTransition(step) {
    state.error = "";
    state.success = "";
    await request(`/funnel-steps/${step.id}`, {
      method: "PUT",
      body: JSON.stringify(normalizeNullable(step))
    });
    state.success = "Переход сохранён.";
    await loadAll();
  }

  function startBranchCreate(step) {
    chainBranchSourceCode.value = step.code;
    resetBranchDraftForSource(step.code);
  }

  function cancelChainBranchEdit() {
    chainBranchSourceCode.value = "";
    resetBranchDraftForSource("");
  }

  function stepTitleByCode(code) {
    return state.funnelSteps.find((item) => item.code === code)?.title || "Конец цепочки";
  }

  const recentEvents = computed(() => state.dashboard?.recent_events || []);
  const conversionTop = computed(() => state.conversions?.top_drop_off_steps || []);
  const newLeadsCount = computed(() => state.leads.filter((l) => l.status === "new").length);
  const paymentList = computed(() => state.accounting?.recent_payments || []);
  const activeTabMeta = computed(() => tabMeta[state.activeTab] || { label: state.activeTab, description: "" });
  const nextStepOptions = computed(() => orderedSteps.value.filter((item) => item.id !== stepDraft.id));
  const triggerStepOptions = computed(() => orderedSteps.value);
  const sortedAutomations = computed(() =>
    [...state.automations].sort((a, b) => (a.inactivity_hours || 0) - (b.inactivity_hours || 0) || (a.id || 0) - (b.id || 0))
  );

  const branchesForCurrentStep = computed(() =>
    state.funnelBranches
      .filter((item) => item.source_step_code === stepDraft.code)
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
  );

  function branchesForStep(sourceStepCode) {
    if (!sourceStepCode) return [];
    return state.funnelBranches
      .filter((item) => item.source_step_code === sourceStepCode)
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
  }

  function targetOptionsFor(sourceStepCode) {
    return orderedSteps.value.filter((item) => item.code !== sourceStepCode);
  }

  const filteredUsers = computed(() => {
    const q = userSearch.value.trim().toLowerCase();
    if (!q) return state.users;
    return state.users.filter(
      (u) =>
        String(u.full_name || "")
          .toLowerCase()
          .includes(q) ||
        String(u.telegram_id || "").includes(q) ||
        String(u.username || "")
          .toLowerCase()
          .includes(q)
    );
  });

  const filteredEvents = computed(() => {
    const q = eventSearch.value.trim().toLowerCase();
    if (!q) return state.events;
    return state.events.filter((e) => {
      const blob = [
        e.event_type,
        e.full_name,
        String(e.telegram_id),
        e.step,
        JSON.stringify(e.payload || {})
      ]
        .join(" ")
        .toLowerCase();
      return blob.includes(q);
    });
  });

  async function handleLogin() {
    state.error = "";
    state.success = "";
    if (!loginForm.username || !loginForm.password) {
      state.error = "Введите логин и пароль.";
      return;
    }

    state.loading = true;
    try {
      const response = await fetch(`${apiBase.value}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: loginForm.username, password: loginForm.password })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Неверный логин или пароль.");
      }
      if (data.status === "must_setup_2fa") {
        authPhase.value = "setup2fa";
        setup2faToken.value = data.setup_token;
        setup2faProvisioningUri.value = data.provisioning_uri || "";
        setup2faSecret.value = data.secret_manual || "";
        loginForm.password = "";
        state.success = "Подключите приложение для кодов (Google Authenticator и аналоги) и введите 6 цифр ниже.";
        return;
      }
      if (data.status === "need_totp") {
        authPhase.value = "totp";
        partialToken.value = data.partial_token;
        loginForm.password = "";
        totpCode.value = "";
        return;
      }
      state.error = "Неожиданный ответ сервера.";
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
    }
  }

  async function submitTotp() {
    state.error = "";
    state.success = "";
    state.loading = true;
    try {
      const response = await fetch(`${apiBase.value}/auth/verify-2fa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ partial_token: partialToken.value, code: totpCode.value })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Неверный код");
      }
      applyAccessToken(data.access_token);
      const me = await fetch(`${apiBase.value}/auth/me`, { headers: authHeaders() });
      if (me.ok) sessionUser.value = await me.json();
      await loadAll();
      resetStepDraft();
      state.success = "";
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
    }
  }

  async function submitSetup2fa() {
    state.error = "";
    state.success = "";
    state.loading = true;
    try {
      const response = await fetch(`${apiBase.value}/auth/confirm-2fa-setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ setup_token: setup2faToken.value, code: totpCode.value })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Неверный код");
      }
      applyAccessToken(data.access_token);
      const me = await fetch(`${apiBase.value}/auth/me`, { headers: authHeaders() });
      if (me.ok) sessionUser.value = await me.json();
      await loadAll();
      resetStepDraft();
      state.success = "Двухфакторная защита включена. Сохраните резервные коды в приложении при необходимости.";
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
    }
  }

  function cancelTotpStep() {
    authPhase.value = "password";
    partialToken.value = "";
    setup2faToken.value = "";
    setup2faProvisioningUri.value = "";
    setup2faSecret.value = "";
    totpCode.value = "";
    state.error = "";
    state.success = "";
  }

  async function tryRestoreSession() {
    const t = typeof localStorage !== "undefined" ? localStorage.getItem(TOKEN_STORAGE) : null;
    if (!t) {
      resetStepDraft();
      return;
    }
    accessToken.value = t;
    state.loading = true;
    state.error = "";
    try {
      const me = await fetch(`${apiBase.value}/auth/me`, { headers: { Authorization: `Bearer ${t}` } });
      if (!me.ok) throw new Error();
      sessionUser.value = await me.json();
      isAuthenticated.value = true;
      await loadAll();
      resetStepDraft();
    } catch {
      clearSession();
    } finally {
      state.loading = false;
    }
  }

  async function setLeadStatus(leadId, status) {
    state.error = "";
    state.success = "";
    try {
      await request(`/leads/${leadId}`, { method: "PATCH", body: JSON.stringify({ status }) });
      state.success = "Статус заявки обновлён.";
      await loadAll();
    } catch (error) {
      state.error = error.message;
    }
  }

  async function loadAdmins() {
    state.error = "";
    try {
      adminsList.value = await request("/admins");
    } catch (error) {
      state.error = error.message;
    }
  }

  async function createAdminUser() {
    state.error = "";
    state.success = "";
    if (!newAdminForm.username.trim() || newAdminForm.password.length < 8) {
      state.error = "Логин и пароль не короче 8 символов.";
      return;
    }
    state.loading = true;
    try {
      await request("/admins", {
        method: "POST",
        body: JSON.stringify({ username: newAdminForm.username.trim(), password: newAdminForm.password })
      });
      newAdminForm.username = "";
      newAdminForm.password = "";
      state.success = "Администратор добавлен. При первом входе ему нужно будет настроить 2FA.";
      await loadAdmins();
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
    }
  }

  async function deleteAdminUser(adminId) {
    if (!confirm("Отключить этого администратора? Войти под ним больше не получится.")) return;
    state.error = "";
    state.success = "";
    state.loading = true;
    try {
      await request(`/admins/${adminId}`, { method: "DELETE" });
      state.success = "Администратор отключён.";
      await loadAdmins();
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
    }
  }

  function logout() {
    clearSession();
    loginForm.username = "";
    loginForm.password = "";
    state.activeTab = "dashboard";
    state.error = "";
    state.success = "";
    adminsList.value = [];
    state.leads = [];
  }

  onMounted(() => {
    resetStepDraft();
    tryRestoreSession();
  });

  return {
    apiBase,
    loginForm,
    isAuthenticated,
    sessionUser,
    authPhase,
    totpCode,
    setup2faQrUrl,
    setup2faSecret,
    userSearch,
    eventSearch,
    adminsList,
    newAdminForm,
    tabGroups,
    state,
    chainBranchSourceCode,
    branchTypeRef,
    stepDraft,
    branchDraft,
    automationDraft,
    recentEvents,
    conversionTop,
    newLeadsCount,
    paymentList,
    orderedSteps,
    activeTabMeta,
    nextSortOrder,
    nextStepOptions,
    triggerStepOptions,
    branchesForCurrentStep,
    sortedAutomations,
    filteredUsers,
    filteredEvents,
    resetStepDraft,
    resetBranchDraft,
    resetBranchDraftForSource,
    resetAutomationDraft,
    stepTypeLabel,
    mediaTypeLabel,
    mediaPreviewUrl,
    isImagePreview,
    isVideoPreview,
    transitionLabel,
    buttonsLabel,
    tabLabel,
    uploadAdminFile,
    loadAll,
    editStep,
    createStepAfter,
    editBranch,
    editAutomation,
    saveStep,
    saveBranch,
    deleteBranch,
    deleteStep,
    deleteAllSteps,
    saveAutomation,
    saveSetting,
    addDeliveryButton,
    removeDeliveryButton,
    saveStepOrder,
    moveStep,
    updateStepTransition,
    startBranchCreate,
    cancelChainBranchEdit,
    stepTitleByCode,
    branchesForStep,
    targetOptionsFor,
    handleLogin,
    submitTotp,
    submitSetup2fa,
    cancelTotpStep,
    loadAdmins,
    createAdminUser,
    deleteAdminUser,
    setLeadStatus,
    logout
  };
}
