const TRANSLATIONS = {
  en: {
    sensor_sensor: "Stop / Station Sensor",
    custom_title: "Custom Title (optional)",
    max_items: "Max departures to show",
    filter_mode: "Filter Mode",
    filter_mode_include: "Whitelist (only show matching)",
    filter_mode_exclude: "Blacklist (hide matching)",
    filter_lines: "Lines Filter (comma-separated, optional)",
    filter_destinations: "Destinations Filter (comma-separated, optional)",
    select_sensor: "Select stop sensor in card settings",
    sensor_not_found: "Sensor {entity} not found",
    no_departures: "No upcoming departures",
    now: "Now",
    min: "min",
    just_now: "Just now",
    sec_ago: "{s}s ago",
    min_ago: "{m}m ago",
    update_error: "Failed to update data",
    starting: "Home Assistant is starting. Not everything may be available yet.",
    card_name: "Valencia Transit Board",
    card_desc: "Real-time departure board for EMT Valencia and Metrovalencia",
    close: "Close",
    more_info: "Entity details",
  },
  ru: {
    sensor_sensor: "Сенсор остановки / станции",
    custom_title: "Свой заголовок (необязательно)",
    max_items: "Максимум отправлений",
    filter_mode: "Режим фильтрации",
    filter_mode_include: "Белый список (показывать только совпадения)",
    filter_mode_exclude: "Чёрный список (скрывать совпадения)",
    filter_lines: "Фильтр линий (через запятую, необязательно)",
    filter_destinations: "Фильтр направлений (через запятую, необязательно)",
    select_sensor: "Выберите сенсор остановки в настройках карточки",
    sensor_not_found: "Сенсор {entity} не найден",
    no_departures: "Нет ближайших отправлений",
    now: "Сейчас",
    min: "мин",
    just_now: "Только что",
    sec_ago: "{s} с назад",
    min_ago: "{m} мин назад",
    update_error: "Не удалось обновить данные",
    starting: "Home Assistant запускается. Некоторые компоненты могут быть ещё недоступны.",
    card_name: "Табло транспорта Валенсии",
    card_desc: "Табло отправлений EMT València и Metrovalencia в реальном времени",
    close: "Закрыть",
    more_info: "Сведения о сущности",
  },
  es: {
    sensor_sensor: "Sensor de parada / estación",
    custom_title: "Título personalizado (opcional)",
    max_items: "Máximo de salidas para mostrar",
    filter_mode: "Modo de filtrado",
    filter_mode_include: "Lista blanca (mostrar solo coincidencias)",
    filter_mode_exclude: "Lista negra (ocultar coincidencias)",
    filter_lines: "Filtro de líneas (separadas por comas, opcional)",
    filter_destinations: "Filtro de destinos (separados por comas, opcional)",
    select_sensor: "Selecciona el sensor de parada en los ajustes de la tarjeta",
    sensor_not_found: "No se ha encontrado el sensor {entity}",
    no_departures: "No hay próximas salidas",
    now: "Ahora",
    min: "min",
    just_now: "Ahora mismo",
    sec_ago: "hace {s} s",
    min_ago: "hace {m} min",
    update_error: "Error al actualizar los datos",
    starting: "Home Assistant se está iniciando. Es posible que aún no esté todo disponible.",
    card_name: "Panel de transporte de Valencia",
    card_desc: "Panel de salidas en tiempo real para EMT València y Metrovalencia",
    close: "Cerrar",
    more_info: "Detalles de la entidad",
  },
  ca: {
    sensor_sensor: "Sensor de parada / estació",
    custom_title: "Títol personalitzat (opcional)",
    max_items: "Màxim d'eixides a mostrar",
    filter_mode: "Mode de filtratge",
    filter_mode_include: "Llista blanca (mostra només coincidències)",
    filter_mode_exclude: "Llista negra (oculta coincidències)",
    filter_lines: "Filtre de línies (separades per comes, opcional)",
    filter_destinations: "Filtre de destinacions (separades per comes, opcional)",
    select_sensor: "Selecciona el sensor de parada en la configuració de la targeta",
    sensor_not_found: "No s'ha trobat el sensor {entity}",
    no_departures: "No hi ha pròximes eixides",
    now: "Ara",
    min: "min",
    just_now: "Ara mateix",
    sec_ago: "fa {s} s",
    min_ago: "fa {m} min",
    update_error: "Error en actualitzar les dades",
    starting: "Home Assistant s'està iniciant. És possible que encara no estiga tot disponible.",
    card_name: "Tauler de transport de València",
    card_desc: "Tauler d'eixides en temps real per a EMT València i Metrovalencia",
    close: "Tancar",
    more_info: "Detalls de l'entitat",
  },
};
TRANSLATIONS.va = TRANSLATIONS.ca;

function getTranslations(lang) {
  const raw = String(lang || "en").trim().toLowerCase();
  if (Object.prototype.hasOwnProperty.call(TRANSLATIONS, raw)) {
    return TRANSLATIONS[raw];
  }
  const base = raw.split(/[-_]/)[0];
  if (base === "val") {
    return TRANSLATIONS.ca;
  }
  if (Object.prototype.hasOwnProperty.call(TRANSLATIONS, base)) {
    return TRANSLATIONS[base];
  }
  return TRANSLATIONS.en;
}

function getEditorSchema(t = TRANSLATIONS.en) {
  return [
    {
      name: "entity",
      required: true,
      selector: {
        entity: {
          domain: "sensor",
        },
      },
    },
    {
      name: "title",
      selector: {
        text: {},
      },
    },
    {
      name: "max_items",
      default: 5,
      selector: {
        number: {
          min: 1,
          max: 15,
          mode: "slider",
        },
      },
    },
    {
      name: "filter_mode",
      default: "include",
      selector: {
        select: {
          mode: "dropdown",
          options: [
            { value: "include", label: t.filter_mode_include },
            { value: "exclude", label: t.filter_mode_exclude },
          ],
        },
      },
    },
    {
      name: "filter_lines",
      selector: {
        text: {},
      },
    },
    {
      name: "filter_destinations",
      selector: {
        text: {},
      },
    },
  ];
}

const EDITOR_SCHEMA = getEditorSchema();

// Background / foreground pairs, adapted from the official line hues.
const METRO_LINE_COLORS = {
  light: {
    1: ["#F5E6B3", "#7E6611"],
    2: ["#EABDD7", "#6C224D"],
    3: ["#F3B4BC", "#7B1421"],
    4: ["#BDCBEA", "#22396D"],
    5: ["#BFE2D2", "#345B49"],
    6: ["#C5C3E2", "#37355A"],
    7: ["#F1D5B6", "#784917"],
    8: ["#BFDBE9", "#25536A"],
    9: ["#E4D3C1", "#5F4930"],
    10: ["#D9EDBA", "#51721D"],
  },
  dark: {
    1: ["#4E4423", "#F2DF9C"],
    2: ["#472A3A", "#E4AACB"],
    3: ["#4C2429", "#EF9FA8"],
    4: ["#293347", "#A9BCE4"],
    5: ["#304039", "#B8D6C8"],
    6: ["#31313F", "#BAB9D5"],
    7: ["#4B3925", "#EDC8A1"],
    8: ["#2B3D46", "#ACD0E2"],
    9: ["#41392F", "#DAC8B4"],
    10: ["#3C4927", "#CEE8A6"],
  },
};

const CARD_STYLES = `
  :host {
    display: block;
    min-width: 0;
    font-family: var(--ha-font-family-body, inherit);
    font-size: var(--ha-font-size-m, 14px);
    color: var(--primary-text-color);
  }
  ha-card {
    height: 100%;
    position: relative;
    overflow: hidden;
  }
  ha-card.interactive {
    cursor: pointer;
    --ha-ripple-color: var(--secondary-text-color);
    --ha-ripple-hover-opacity: 0.04;
    --ha-ripple-pressed-opacity: 0.12;
  }
  ha-card.interactive:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--ha-space-3, 12px);
    padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px) 0;
  }
  .card-content {
    padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px) var(--ha-space-4, 16px);
    margin-top: 0;
  }
  .name, .dest {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .name {
    font-size: var(--ha-tile-info-primary-font-size, var(--ha-font-size-m, 14px));
    font-weight: var(--ha-tile-info-primary-font-weight, var(--ha-font-weight-medium, 500));
    line-height: var(--ha-tile-info-primary-line-height, var(--ha-line-height-normal, 20px));
    letter-spacing: var(--ha-tile-info-primary-letter-spacing, 0.1px);
    color: var(--ha-tile-info-primary-color, var(--primary-text-color));
  }
  .status-meta {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    white-space: nowrap;
    gap: var(--ha-space-1, 4px);
    font-size: var(--ha-tile-info-secondary-font-size, var(--ha-font-size-s, 12px));
    font-weight: var(--ha-tile-info-secondary-font-weight, var(--ha-font-weight-normal, 400));
    line-height: var(--ha-tile-info-secondary-line-height, var(--ha-line-height-condensed, 16px));
    letter-spacing: var(--ha-tile-info-secondary-letter-spacing, 0.4px);
    color: var(--ha-tile-info-secondary-color, var(--secondary-text-color));
  }
  .error-icon {
    display: inline-flex;
    color: var(--error-color);
    --mdc-icon-size: 14px;
    cursor: help;
  }
  .list {
    display: flex;
    flex-direction: column;
    gap: var(--entities-card-row-gap, var(--card-row-gap, 8px));
  }
  .row {
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr) max-content;
    align-items: center;
    gap: var(--ha-space-4, 16px);
    min-height: 40px;
  }
  .line-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    width: 40px;
    min-height: 32px;
    padding: 4px 2px;
    border-radius: var(--ha-border-radius-sm, 4px);
    font-weight: var(--ha-font-weight-bold, 700);
    line-height: 24px;
  }
  .time {
    color: var(--primary-text-color);
    font-weight: var(--ha-font-weight-medium, 500);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .time.soon {
    color: var(--success-color, #43A047);
  }
  .empty {
    display: flex;
    align-items: center;
    min-height: 40px;
    color: var(--secondary-text-color);
  }
  .placeholder { padding: var(--ha-space-4, 16px); }
  .warning { border-width: 0; }
  .warning::after {
    position: absolute;
    inset: 0;
    content: "";
    background-color: var(--warning-color, #FF9800);
    opacity: 0.12;
    pointer-events: none;
    border-radius: inherit;
  }
  .warning-content {
    display: flex;
    align-items: center;
    gap: var(--ha-space-2, 8px);
    padding: var(--ha-space-4, 16px);
  }
  .warning-content ha-icon {
    flex: 0 0 24px;
    color: var(--warning-color, #FF9800);
  }
  .warning-message { min-width: 0; overflow-wrap: anywhere; }
  .schedule-dialog {
    width: min(92vw, 480px);
    max-width: 480px;
    max-height: min(85vh, 680px);
    margin: auto;
    padding: 0;
    border: none;
    border-radius: var(--ha-dialog-border-radius, var(--ha-border-radius-lg, 16px));
    background: var(--ha-dialog-surface-background, var(--card-background-color, var(--primary-background-color, #fff)));
    color: var(--primary-text-color);
    box-shadow: var(--ha-dialog-box-shadow, 0 8px 32px rgba(0, 0, 0, 0.28));
    overflow: hidden;
  }
  .schedule-dialog[open] {
    display: flex;
    flex-direction: column;
  }
  .schedule-dialog::backdrop {
    background: var(--mdc-dialog-scrim-color, rgba(0, 0, 0, 0.6));
  }
  .dialog-header {
    display: flex;
    align-items: center;
    gap: var(--ha-space-2, 8px);
    padding: var(--ha-space-3, 12px);
    border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2));
    flex-shrink: 0;
  }
  .dialog-title-wrap {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .dialog-title {
    font-size: var(--ha-font-size-l, 16px);
    font-weight: var(--ha-font-weight-medium, 500);
    line-height: 22px;
    color: var(--primary-text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--secondary-text-color);
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 150ms ease, color 150ms ease;
  }
  .icon-btn:hover {
    background-color: rgba(127, 127, 127, 0.12);
    color: var(--primary-text-color);
  }
  .icon-btn:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .dialog-content {
    padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px) var(--ha-space-4, 16px);
    overflow-y: auto;
    overscroll-behavior: contain;
    flex: 1 1 auto;
  }
`;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function parseFilterList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item ?? "").trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
  }
  if (typeof value === "number") {
    return [String(value)];
  }
  return [];
}

function normalizeLine(value) {
  return String(value ?? "").trim().replace(/^L\s*/i, "").toLowerCase();
}

function normalizeText(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function normalizeFilterMode(mode) {
  const raw = String(mode ?? "").trim().toLowerCase();
  if (raw === "exclude" || raw === "blacklist") {
    return "exclude";
  }
  return "include";
}

// Card editor component
class VlcTransportHaCardEditor extends HTMLElement {
  setConfig(config) {
    const normalized = {
      max_items: 5,
      filter_mode: "include",
      ...config,
    };
    normalized.filter_mode = normalizeFilterMode(normalized.filter_mode);
    if (Array.isArray(normalized.filter_lines)) {
      normalized.filter_lines = normalized.filter_lines.join(", ");
    }
    if (Array.isArray(normalized.filter_destinations)) {
      normalized.filter_destinations = normalized.filter_destinations.join(", ");
    }
    this._config = normalized;
    this._updateForm();
  }

  set hass(hass) {
    this._hass = hass;
    this._updateForm();
  }

  _updateForm() {
    if (!this._hass || !this._config) return;

    const t = getTranslations(this._hass?.language);

    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => {
        const currentT = getTranslations(this._hass?.language);
        const labels = {
          entity: currentT.sensor_sensor,
          title: currentT.custom_title,
          max_items: currentT.max_items,
          filter_mode: currentT.filter_mode,
          filter_lines: currentT.filter_lines,
          filter_destinations: currentT.filter_destinations,
        };
        return labels[schema.name] || schema.name;
      };

      this._form.addEventListener("value-changed", (ev) => {
        const newConfig = { ...ev.detail.value };
        if (!newConfig.title) {
          delete newConfig.title;
        }
        if (!newConfig.filter_lines || !String(newConfig.filter_lines).trim()) {
          delete newConfig.filter_lines;
        }
        if (!newConfig.filter_destinations || !String(newConfig.filter_destinations).trim()) {
          delete newConfig.filter_destinations;
        }
        if (
          !newConfig.filter_lines &&
          !newConfig.filter_destinations &&
          normalizeFilterMode(newConfig.filter_mode) === "include"
        ) {
          delete newConfig.filter_mode;
        }
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: newConfig },
            bubbles: true,
            composed: true,
          })
        );
      });

      this.appendChild(this._form);
    }

    this._form.schema = getEditorSchema(t);
    this._form.hass = this._hass;
    this._form.data = this._config;
  }
}

customElements.define("vlc-transport-ha-card-editor", VlcTransportHaCardEditor);

// Main board card component
class VlcTransportHaCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._cache = null;
    this._tickInterval = null;
    this._renderedRows = 0;
    this._isPlaceholder = true;
    this._dialogOpen = false;
    this._systemTheme = window.matchMedia?.("(prefers-color-scheme: dark)");
    this._onSystemThemeChange = () => {
      if (typeof this._hass?.themes?.darkMode !== "boolean") {
        this._renderFromHass();
      }
    };
    this._onShadowClick = (ev) => {
      const target = ev?.target;
      if (!target || typeof target.closest !== "function") return;
      if (target.closest(".dialog-close")) {
        ev.stopPropagation?.();
        this._closeDialog();
        return;
      }
      if (target.closest(".dialog-more-info")) {
        ev.stopPropagation?.();
        this._openMoreInfo();
        return;
      }
      const dialog = target.closest(".schedule-dialog");
      if (dialog) {
        if (target === dialog) {
          this._closeDialog();
        }
        return;
      }
      if (target.closest("ha-card.interactive")) {
        this._openDialog();
      }
    };
    this._onShadowKeyDown = (ev) => {
      if (ev?.key === "Escape" && this._dialogOpen) {
        ev.preventDefault?.();
        this._closeDialog();
        return;
      }
      if (
        (ev?.key === "Enter" || ev?.key === " ") &&
        !this._dialogOpen &&
        !this._isPlaceholder &&
        ev?.target?.closest?.("ha-card.interactive")
      ) {
        ev.preventDefault?.();
        this._openDialog();
      }
    };
    this.shadowRoot.addEventListener?.("click", this._onShadowClick);
    this.shadowRoot.addEventListener?.("keydown", this._onShadowKeyDown);
  }

  static getConfigElement() {
    return document.createElement("vlc-transport-ha-card-editor");
  }

  static getStubConfig(hass) {
    const matchingEntity = Object.keys(hass.states).find((entityId) => {
      if (!entityId.startsWith("sensor.")) return false;
      const attrs = hass.states[entityId]?.attributes || {};
      return attrs.provider === "emt" || attrs.provider === "metrovalencia";
    });

    return {
      entity: matchingEntity || "",
      max_items: 5,
    };
  }

  connectedCallback() {
    this._systemTheme?.addEventListener("change", this._onSystemThemeChange);
    this._renderFromHass();
    // Re-render relative timestamps and expire departures every ten seconds.
    if (!this._tickInterval) {
      this._tickInterval = setInterval(() => {
        if (this._hass && this.config) {
          this._renderFromHass();
        }
      }, 10000);
    }
  }

  disconnectedCallback() {
    this._systemTheme?.removeEventListener("change", this._onSystemThemeChange);
    this._dialogOpen = false;
    if (this._tickInterval) {
      clearInterval(this._tickInterval);
      this._tickInterval = null;
    }
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    if (this.config && this.config.entity !== config.entity) {
      this._cache = null;
      this._dialogOpen = false;
    }
    this.config = {
      max_items: 5,
      ...config,
    };
    if (this._hass) {
      this._renderFromHass();
    }
  }

  _openDialog() {
    if (this._isPlaceholder || this._dialogOpen) return;
    this._dialogOpen = true;
    this._renderFromHass();
  }

  _closeDialog() {
    if (!this._dialogOpen) return;
    this._dialogOpen = false;
    const dialog = this.shadowRoot?.querySelector?.(".schedule-dialog");
    if (dialog && typeof dialog.close === "function" && dialog.open) {
      try {
        dialog.close();
      } catch (_err) {
        // Ignore if dialog is not open in DOM
      }
    }
    this._renderFromHass();
  }

  _openMoreInfo() {
    const entityId = this.config?.entity;
    this._closeDialog();
    if (!entityId) return;
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      })
    );
  }

  set hass(hass) {
    this._hass = hass;
    this._renderFromHass();
  }

  _getTranslations() {
    return getTranslations(this._hass?.language);
  }

  _getBadgeColors(provider, line) {
    if (provider === "emt") return ["#E30613", "#FFFFFF"];
    const darkMode = this._hass?.themes?.darkMode;
    const isDark = typeof darkMode === "boolean" ? darkMode : Boolean(this._systemTheme?.matches);
    const normalizedLine = String(line ?? "").trim().replace(/^L\s*/i, "");
    const colors = METRO_LINE_COLORS[isDark ? "dark" : "light"];
    if (Object.prototype.hasOwnProperty.call(colors, normalizedLine)) {
      return colors[normalizedLine];
    }
    return ["var(--secondary-background-color, var(--primary-background-color))", "var(--primary-text-color)"];
  }

  _matchesFilter(departure) {
    const lineTokens = parseFilterList(this.config?.filter_lines).map(normalizeLine).filter(Boolean);
    const destTokens = parseFilterList(this.config?.filter_destinations).map(normalizeText).filter(Boolean);
    const hasLineFilter = lineTokens.length > 0;
    const hasDestFilter = destTokens.length > 0;

    if (!hasLineFilter && !hasDestFilter) {
      return true;
    }

    const depLine = normalizeLine(departure?.line);
    const depDest = normalizeText(departure?.destination);

    const lineMatches = hasLineFilter && lineTokens.includes(depLine);
    const destMatches = hasDestFilter && destTokens.some((token) => depDest.includes(token));

    const mode = normalizeFilterMode(this.config?.filter_mode);
    if (mode === "exclude") {
      return !(lineMatches || destMatches);
    }
    return (!hasLineFilter || lineMatches) && (!hasDestFilter || destMatches);
  }

  _getCurrentDepartures(departures, { applyFilters = true, applyLimit = true } = {}) {
    const now = Date.now();
    const filtered = departures.filter((departure) => {
      if (departure.timestamp) {
        const targetMs = Date.parse(departure.timestamp);
        if (!isNaN(targetMs) && targetMs < now - 30000) {
          return false;
        }
      }
      return applyFilters ? this._matchesFilter(departure) : true;
    });
    if (!applyLimit) {
      return filtered;
    }
    return filtered.slice(0, Number(this.config.max_items) || 5);
  }

  // Compute remaining departure time in rounded minutes, or null if unknown
  _getDepartureMinutes(dep) {
    if (dep.timestamp) {
      const targetMs = Date.parse(dep.timestamp);
      if (!isNaN(targetMs)) {
        const diffSec = (targetMs - Date.now()) / 1000;
        return Math.max(0, Math.round(diffSec / 60));
      }
    }

    const exactTime = dep.time || dep.minutes || "—";
    if (typeof exactTime === "string" && exactTime.includes(":")) {
      const parts = exactTime.split(":");
      if (parts.length >= 2) {
        const hours = parseInt(parts[0], 10);
        const minutes = parseInt(parts[1], 10);
        if (!isNaN(hours) && !isNaN(minutes)) {
          const now = new Date();
          const target = new Date(now);
          target.setHours(hours, minutes, 0, 0);
          let diffSec = (target.getTime() - now.getTime()) / 1000;
          if (diffSec < -600) diffSec += 86400;
          return Math.max(0, Math.round(diffSec / 60));
        }
      }
    }

    return null;
  }

  // Format departure time: < 60 min as relative minutes, >= 60 min as exact HH:MM
  _formatDepartureTime(dep, t) {
    const exactTime = dep.time || dep.minutes || "—";
    const diffMin = this._getDepartureMinutes(dep);

    if (diffMin !== null) {
      if (diffMin === 0) return t.now;
      if (diffMin < 60) return `${diffMin} ${t.min}`;
    }

    return exactTime;
  }

  // Format header update timestamp: < 60s in seconds, < 60m in minutes, >= 60m as exact HH:MM
  _formatLastUpdated(isoString, t) {
    if (!isoString) return "";
    const updatedMs = Date.parse(isoString);
    if (isNaN(updatedMs)) return "";

    const diffSec = Math.max(0, Math.floor((Date.now() - updatedMs) / 1000));
    if (diffSec < 10) return t.just_now;
    if (diffSec < 60) {
      const roundedSec = Math.floor(diffSec / 10) * 10;
      return t.sec_ago.replace("{s}", roundedSec);
    }

    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return t.min_ago.replace("{m}", diffMin);

    const dateObj = new Date(updatedMs);
    return dateObj.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  _renderFromHass() {
    if (!this.config || !this._hass) return;
    const t = this._getTranslations();

    if (!this.config.entity) {
      this.renderPlaceholder(t.select_sensor);
      return;
    }

    const stateObj = this._hass.states[this.config.entity];
    if (!stateObj && this._hass.config?.state === "NOT_RUNNING") {
      this.renderPlaceholder(
        this._hass.localize?.("ui.panel.lovelace.warning.starting") || t.starting,
        true
      );
      return;
    }
    if (!stateObj && !this._cache) {
      this.renderPlaceholder(
        this._hass.localize?.("ui.panel.lovelace.warning.entity_not_found", "entity", this.config.entity) ||
          t.sensor_not_found.replace("{entity}", this.config.entity),
        true
      );
      return;
    }

    const attrs = stateObj?.attributes || {};
    const hasValidData = stateObj && stateObj.state !== "unavailable" &&
      !attrs.update_failed && Array.isArray(attrs.departures);
    const isUnavailable = !stateObj || stateObj.state === "unavailable" ||
      (stateObj.state === "unknown" && !hasValidData);
    const hasError = isUnavailable || Boolean(attrs.update_failed);
    const errorMessage = attrs.last_error || t.update_error;
    const lastUpdated = Object.prototype.hasOwnProperty.call(attrs, "last_updated")
      ? attrs.last_updated : stateObj?.last_updated;

    // Update local cache whenever valid attributes are present
    if (hasValidData) {
      this._cache = {
        title:
          this.config.title || attrs.friendly_name || this.config.entity,
        stopTitle:
          attrs.friendly_name || this.config.title || this.config.entity,
        provider: attrs.provider || "emt",
        departures: attrs.departures,
        lastUpdated,
      };
    } else if (!this._cache && stateObj) {
      this._cache = {
        title:
          this.config.title || attrs.friendly_name || this.config.entity,
        stopTitle:
          attrs.friendly_name || this.config.title || this.config.entity,
        provider: attrs.provider || "emt",
        departures: Array.isArray(attrs.departures) ? attrs.departures : [],
        lastUpdated,
      };
    }

    const activeData = {
      title: this.config.title || this._cache.title,
      stopTitle:
        attrs.friendly_name ||
        this._cache.stopTitle ||
        this.config.title ||
        this.config.entity,
      provider: this._cache.provider,
      departures: this._cache.departures,
      lastUpdated: attrs.last_updated || this._cache.lastUpdated,
      hasError,
      errorMessage,
    };

    this.render(activeData, t);
  }

  renderPlaceholder(message, warning = false) {
    this._isPlaceholder = true;
    this._dialogOpen = false;
    this._renderedRows = 0;
    this.shadowRoot.innerHTML = `
      <style>${CARD_STYLES}</style>
      <ha-card class="${warning ? "warning" : ""}">
        ${warning ? `
          <div class="warning-content" role="alert">
            <ha-icon icon="mdi:alert-outline" aria-hidden="true"></ha-icon>
            <span class="warning-message">${escapeHtml(message)}</span>
          </div>` : `<div class="placeholder">${escapeHtml(message)}</div>`}
      </ha-card>
    `;
  }

  _renderRows(departuresList, provider, t) {
    if (!departuresList.length) {
      return `<div class="empty">${escapeHtml(t.no_departures)}</div>`;
    }
    return departuresList
      .map((d) => {
        const diffMin = this._getDepartureMinutes(d);
        const timeLabel = this._formatDepartureTime(d, t);
        const timeClass = diffMin !== null && diffMin < 5 ? "time soon" : "time";
        const [background, color] = this._getBadgeColors(provider, d.line);
        return `
          <div class="row">
            <span class="line-badge" style="background:${background};color:${color}">${escapeHtml(d.line || "—")}</span>
            <span class="dest" title="${escapeHtml(d.destination || "")}">${escapeHtml(d.destination || "")}</span>
            <span class="${timeClass}">${escapeHtml(timeLabel)}</span>
          </div>
        `;
      })
      .join("");
  }

  render(data, t) {
    const { title, stopTitle, provider, departures, lastUpdated, hasError, errorMessage } = data;
    const updatedLabel = this._formatLastUpdated(lastUpdated, t);
    const prevScrollTop = this._dialogOpen
      ? this.shadowRoot?.querySelector?.(".dialog-content")?.scrollTop ?? 0
      : 0;

    const currentDepartures = this._getCurrentDepartures(departures);
    this._isPlaceholder = false;
    this._renderedRows = currentDepartures.length;
    const rowsHtml = this._renderRows(currentDepartures, provider, t);
    const errorIconHtml = hasError
      ? `<ha-icon class="error-icon" icon="mdi:alert-circle-outline" title="${escapeHtml(errorMessage)}" aria-label="${escapeHtml(errorMessage)}"></ha-icon>`
      : "";

    let dialogHtml = "";
    if (this._dialogOpen) {
      const allDepartures = this._getCurrentDepartures(departures, {
        applyFilters: false,
        applyLimit: false,
      });
      const modalRowsHtml = this._renderRows(allDepartures, provider, t);
      dialogHtml = `
        <dialog class="schedule-dialog" open aria-label="${escapeHtml(stopTitle)}">
          <div class="dialog-header">
            <button class="icon-btn dialog-close" type="button" title="${escapeHtml(t.close)}" aria-label="${escapeHtml(t.close)}">
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
            <div class="dialog-title-wrap">
              <div class="dialog-title" title="${escapeHtml(stopTitle)}">${escapeHtml(stopTitle)}</div>
              <div class="status-meta">
                ${errorIconHtml}
                <span>${escapeHtml(updatedLabel)}</span>
              </div>
            </div>
            <button class="icon-btn dialog-more-info" type="button" title="${escapeHtml(t.more_info)}" aria-label="${escapeHtml(t.more_info)}">
              <ha-icon icon="mdi:information-outline" aria-hidden="true"></ha-icon>
            </button>
          </div>
          <div class="dialog-content"><div class="list">${modalRowsHtml}</div></div>
        </dialog>
      `;
    }

    this.shadowRoot.innerHTML = `
      <style>${CARD_STYLES}</style>
      <ha-card class="interactive" tabindex="0" role="button" aria-haspopup="dialog">
        <ha-ripple></ha-ripple>
        <div class="card-header">
          <div class="name" title="${escapeHtml(title)}">${escapeHtml(title)}</div>
          <div class="status-meta">
            ${errorIconHtml}
            <span>${escapeHtml(updatedLabel)}</span>
          </div>
        </div>
        <div class="card-content"><div class="list">${rowsHtml}</div></div>
      </ha-card>
      ${dialogHtml}
    `;

    if (this._dialogOpen && this.shadowRoot?.querySelector) {
      const dialog = this.shadowRoot.querySelector(".schedule-dialog");
      if (dialog) {
        if (typeof dialog.showModal === "function") {
          try {
            dialog.removeAttribute("open");
            dialog.showModal();
          } catch (_err) {
            dialog.setAttribute("open", "");
          }
        }
        dialog.addEventListener?.("close", () => {
          if (this._dialogOpen) {
            this._dialogOpen = false;
            this._renderFromHass();
          }
        });
        const contentEl = dialog.querySelector?.(".dialog-content");
        if (contentEl && prevScrollTop > 0) {
          contentEl.scrollTop = prevScrollTop;
        }
      }
    }
  }

  getCardSize() {
    return this._isPlaceholder ? 1 : 2 + Math.max(1, this._renderedRows);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }
}

customElements.define("vlc-transport-ha-card", VlcTransportHaCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "vlc-transport-ha-card",
  name: "Valencia Transit Board",
  description: "Real-time departure board for EMT Valencia and Metrovalencia",
  preview: true,
});
