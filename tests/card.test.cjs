const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const now = Date.parse('2026-11-13T12:00:00Z');
class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [now])); }
  static now() { return now; }
}
const context = {
  HTMLElement: class {
    attachShadow() { this.shadowRoot = { innerHTML: '' }; }
    appendChild(child) { this._child = child; }
    dispatchEvent(ev) { this._lastEvent = ev; }
  },
  CustomEvent: class {
    constructor(type, init) { this.type = type; this.detail = init?.detail; }
  },
  document: {
    createElement(tag) {
      return {
        tagName: tag,
        addEventListener(type, fn) { this._listener = fn; },
      };
    },
  },
  customElements: { define() {} }, window: {}, Date: FixedDate, setInterval, clearInterval,
};
vm.createContext(context);
const cardFile = path.join(__dirname, '../custom_components/vlc_transport_ha/frontend/vlc-transport-ha-card.js');
vm.runInContext(fs.readFileSync(cardFile, 'utf8') + '\nthis.Card = VlcTransportHaCard;\nthis.Editor = VlcTransportHaCardEditor;\nthis.TRANSLATIONS = TRANSLATIONS;', context);

function setup() {
  const card = new context.Card();
  card.setConfig({ entity: 'sensor.stop', max_items: 5 });
  return card;
}
function setState(card, state, attributes, entity = 'sensor.stop', hassExtras = {}) {
  card.hass = { ...hassExtras, states: { [entity]: { state, attributes, last_updated: '2026-11-13T11:59:30Z' } } };
}
const future = { line: '7', destination: 'Centre', time: '13:05', timestamp: '2026-11-13T12:05:00Z' };

test('successful empty unknown state clears previously cached departures', () => {
  const card = setup();
  setState(card, '13:05', { departures: [future] });
  assert.match(card.shadowRoot.innerHTML, /Centre/);
  setState(card, 'unknown', { departures: [], update_failed: false });
  assert.match(card.shadowRoot.innerHTML, /No upcoming departures/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Centre|mdi:alert-circle-outline/);
});

test('failed update keeps future cached departures and marks the error', () => {
  const card = setup();
  setState(card, '13:05', { departures: [future], last_updated: '2026-11-13T11:59:30Z' });
  setState(card, '13:05', { departures: [], update_failed: true, last_error: 'Offline' });
  assert.match(card.shadowRoot.innerHTML, /Centre/);
  assert.match(card.shadowRoot.innerHTML, /mdi:alert-circle-outline/);
  assert.match(card.shadowRoot.innerHTML, /30s ago/);
});

test('an initial failed update does not present its state change as a successful update', () => {
  const card = setup();
  setState(card, 'unavailable', { departures: [], update_failed: true, last_updated: null });
  assert.match(card.shadowRoot.innerHTML, /mdi:alert-circle-outline/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /30s ago/);
});

test('expired departures disappear after 30 seconds', () => {
  const card = setup();
  setState(card, '13:05', { departures: [
    { ...future, line: 'old', timestamp: '2026-11-13T11:59:29Z' },
    { ...future, line: 'recent', timestamp: '2026-11-13T11:59:30Z' },
    future,
  ] });
  assert.doesNotMatch(card.shadowRoot.innerHTML, />old</);
  assert.match(card.shadowRoot.innerHTML, />recent</);
  assert.match(card.shadowRoot.innerHTML, />Now</);
  assert.match(card.shadowRoot.innerHTML, />5 min</);
});

test('switching to a missing or unavailable entity clears old data', () => {
  const card = setup();
  setState(card, '13:05', { departures: [future] });
  card.setConfig({ entity: 'sensor.other' });
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Centre/);
  assert.match(card.shadowRoot.innerHTML, /sensor.other not found/);
  setState(card, 'unavailable', { departures: [] }, 'sensor.other');
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Centre/);
  assert.match(card.shadowRoot.innerHTML, /mdi:alert-circle-outline/);
});

test('escapes data and error messages in markup and attributes', () => {
  const card = setup();
  const attack = '<img src=x onerror="alert(1)">';
  setState(card, '13:05', {
    friendly_name: attack,
    departures: [{ ...future, line: attack, destination: attack }],
  });
  assert.doesNotMatch(card.shadowRoot.innerHTML, /<img/);
  assert.match(card.shadowRoot.innerHTML, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  setState(card, '13:05', { departures: [], update_failed: true, last_error: attack });
  assert.doesNotMatch(card.shadowRoot.innerHTML, /<img/);
  assert.match(card.shadowRoot.innerHTML, /title="&lt;img/);
  card.setConfig({ entity: attack });
  assert.doesNotMatch(card.shadowRoot.innerHTML, /<img/);
  assert.match(card.shadowRoot.innerHTML, /&lt;img/);
});

function contrastRatio(background, foreground) {
  function luminance(hex) {
    const rgb = hex.slice(1).match(/../g).map((part) => {
      const value = parseInt(part, 16) / 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    });
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  }
  const [low, high] = [luminance(background), luminance(foreground)].sort((a, b) => a - b);
  return (high + 0.05) / (low + 0.05);
}

test('all ten metro lines use distinct readable pairs in both themes', () => {
  const card = setup();
  card.setConfig({ entity: 'sensor.stop', max_items: 15 });
  const departures = Array.from({ length: 10 }, (_, index) => ({ ...future, line: String(index + 1) }));
  for (const darkMode of [false, true]) {
    setState(card, '13:05', { provider: 'metrovalencia', departures }, 'sensor.stop', { themes: { darkMode } });
    const pairs = [...card.shadowRoot.innerHTML.matchAll(/class="line-badge" style="background:(#[A-F0-9]+);color:(#[A-F0-9]+)"/g)];
    assert.equal(pairs.length, 10);
    assert.equal(new Set(pairs.map((pair) => pair[1] + pair[2])).size, 10);
    for (const [, background, foreground] of pairs) {
      assert.ok(contrastRatio(background, foreground) >= 3.0, `${background} / ${foreground}`);
    }
  }
});

test('theme changes recolor existing metro rows, but EMT remains red', () => {
  const card = setup();
  for (const darkMode of [false, true, false]) {
    setState(card, '13:05', { provider: 'metrovalencia', departures: [future] }, 'sensor.stop', { themes: { darkMode } });
    assert.ok(card.shadowRoot.innerHTML.includes(darkMode ? 'background:#4B3925;color:#EDC8A1' : 'background:#F1D5B6;color:#784917'));
    setState(card, '13:05', { provider: 'emt', departures: [{ ...future, line: 'N4' }] }, 'sensor.stop', { themes: { darkMode } });
    assert.match(card.shadowRoot.innerHTML, /background:#E30613;color:#FFFFFF/);
  }
  assert.ok(contrastRatio('#E30613', '#FFFFFF') >= 4.5);
});

test('line colors accept numeric, L-prefixed and spaced identifiers with a neutral fallback', () => {
  const card = setup();
  for (const line of [4, '4', 'L4', ' l 4 ']) {
    assert.deepEqual([...card._getBadgeColors('metrovalencia', line)], ['#BDCBEA', '#22396D']);
  }
  for (const line of ['11', '__proto__', '<img>']) {
    const [background, foreground] = card._getBadgeColors('metrovalencia', line);
    assert.match(background, /var\(--secondary-background-color/);
    assert.equal(foreground, 'var(--primary-text-color)');
  }
});

test('system color scheme is a live fallback and HA mode takes precedence', () => {
  let onChange;
  let removed = false;
  const media = {
    matches: true,
    addEventListener(event, handler) { onChange = handler; },
    removeEventListener(event, handler) { removed = handler === onChange; },
  };
  context.window.matchMedia = () => media;
  const card = setup();
  try {
    setState(card, '13:05', { provider: 'metrovalencia', departures: [future] });
    card.connectedCallback();
    assert.match(card.shadowRoot.innerHTML, /background:#4B3925/);
    media.matches = false;
    onChange();
    assert.match(card.shadowRoot.innerHTML, /background:#F1D5B6/);
    setState(card, '13:05', { provider: 'metrovalencia', departures: [future] }, 'sensor.stop', { themes: { darkMode: true } });
    assert.match(card.shadowRoot.innerHTML, /background:#4B3925/);
  } finally {
    card.disconnectedCallback();
    delete context.window.matchMedia;
  }
  assert.equal(removed, true);
});

test('startup uses the native localized warning and renders data as soon as the entity appears', () => {
  const card = setup();
  const calls = [];
  card.hass = {
    config: { state: 'NOT_RUNNING' }, states: {},
    localize(key) { calls.push(key); return 'Custom localized starting warning'; },
  };
  assert.deepEqual(calls, ['ui.panel.lovelace.warning.starting']);
  assert.match(card.shadowRoot.innerHTML, /class="warning"/);
  assert.match(card.shadowRoot.innerHTML, /Custom localized starting warning/);
  assert.equal(card.getCardSize(), 1);
  setState(card, '13:05', { departures: [future] }, 'sensor.stop', { config: { state: 'NOT_RUNNING' } });
  assert.match(card.shadowRoot.innerHTML, /Centre/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /class="warning"/);
});

test('startup fallback supersedes cached rows and ends when HA finishes starting', () => {
  const card = setup();
  setState(card, '13:05', { departures: [future] });
  card.hass = { states: {}, config: { state: 'NOT_RUNNING' } };
  assert.match(card.shadowRoot.innerHTML, /Home Assistant is starting\. Not everything may be available yet\./);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Centre/);
  const emptyCard = setup();
  emptyCard.hass = { states: {}, config: { state: 'NOT_RUNNING' } };
  emptyCard.hass = { states: {}, config: { state: 'RUNNING' } };
  assert.doesNotMatch(emptyCard.shadowRoot.innerHTML, /Home Assistant is starting/);
  assert.match(emptyCard.shadowRoot.innerHTML, /sensor.stop not found/);
  assert.match(emptyCard.shadowRoot.innerHTML, /class="warning"/);
});

test('card size follows displayed rows including limits, expiry, empty and warning states', () => {
  const card = setup();
  const departures = Array.from({ length: 8 }, () => future);
  setState(card, '13:05', { departures });
  assert.equal(card.getCardSize(), 7);
  card.setConfig({ entity: 'sensor.stop', max_items: 2 });
  assert.equal(card.getCardSize(), 4);
  setState(card, 'unknown', { departures: [] });
  assert.equal(card.getCardSize(), 3);
  setState(card, '13:05', { departures: [{ ...future, timestamp: '2020-01-01T00:00:00Z' }] });
  assert.equal(card.getCardSize(), 3);
  card.setConfig({ entity: 'sensor.missing' });
  assert.equal(card.getCardSize(), 1);
  assert.deepEqual({ ...card.getGridOptions() }, { columns: 12, min_columns: 6, rows: 'auto' });
});

const sampleDepartures = [
  { ...future, line: '4', destination: 'Empalme' },
  { ...future, line: '4', destination: 'Dr. Lluch' },
  { ...future, line: '6', destination: 'Marítim' },
  { ...future, line: '99', destination: 'Palau de Congressos' },
  { ...future, line: 'C3', destination: 'Estació del Nord' },
];

test('whitelist filters by line (including L-prefix and YAML arrays) and destination (case/accent-insensitive substring)', () => {
  const card = setup();
  setState(card, '13:05', { departures: sampleDepartures });

  // Line filter via comma-separated string with L-prefix and case variation
  card.setConfig({ entity: 'sensor.stop', filter_lines: 'L4, c3' });
  assert.match(card.shadowRoot.innerHTML, /Empalme/);
  assert.match(card.shadowRoot.innerHTML, /Dr\. Lluch/);
  assert.match(card.shadowRoot.innerHTML, /Estació del Nord/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Marítim|Palau de Congressos/);

  // Line filter via YAML array
  card.setConfig({ entity: 'sensor.stop', filter_lines: [6, '99'] });
  assert.match(card.shadowRoot.innerHTML, /Marítim/);
  assert.match(card.shadowRoot.innerHTML, /Palau de Congressos/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Empalme|Estació del Nord/);

  // Destination filter with case-insensitive and accent-insensitive substring matching
  card.setConfig({ entity: 'sensor.stop', filter_destinations: 'maritim, estacio' });
  assert.match(card.shadowRoot.innerHTML, /Marítim/);
  assert.match(card.shadowRoot.innerHTML, /Estació del Nord/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Empalme|Dr\. Lluch|Palau/);
});

test('combining line and destination filters uses AND in whitelist and OR in blacklist', () => {
  const card = setup();
  setState(card, '13:05', { departures: sampleDepartures });

  // Whitelist (AND): only line 4 heading to Empalme
  card.setConfig({
    entity: 'sensor.stop',
    filter_mode: 'include',
    filter_lines: '4',
    filter_destinations: 'empalme',
  });
  assert.match(card.shadowRoot.innerHTML, /Empalme/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Dr\. Lluch|Marítim|Palau|Estació/);

  // Blacklist (OR): hide line 4 OR destination containing 'maritim'
  card.setConfig({
    entity: 'sensor.stop',
    filter_mode: 'exclude',
    filter_lines: '4',
    filter_destinations: 'maritim',
  });
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Empalme|Dr\. Lluch|Marítim/);
  assert.match(card.shadowRoot.innerHTML, /Palau de Congressos/);
  assert.match(card.shadowRoot.innerHTML, /Estació del Nord/);

  // Also supports 'blacklist' alias in YAML
  card.setConfig({
    entity: 'sensor.stop',
    filter_mode: 'blacklist',
    filter_destinations: ['lluch', 'palau'],
  });
  assert.match(card.shadowRoot.innerHTML, /Empalme/);
  assert.match(card.shadowRoot.innerHTML, /Marítim/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Dr\. Lluch|Palau/);
});

test('filtering applies before max_items limit', () => {
  const card = setup();
  setState(card, '13:05', { departures: sampleDepartures });
  card.setConfig({
    entity: 'sensor.stop',
    max_items: 2,
    filter_lines: '99, C3',
  });
  assert.equal(card.getCardSize(), 4);
  assert.match(card.shadowRoot.innerHTML, /Palau de Congressos/);
  assert.match(card.shadowRoot.innerHTML, /Estació del Nord/);
});

test('editor normalizes array filters and cleans up empty filter fields on change', () => {
  const editor = new context.Editor();
  editor.hass = { language: 'en', states: {} };
  editor.setConfig({
    entity: 'sensor.stop',
    filter_mode: 'blacklist',
    filter_lines: ['L4', 6],
    filter_destinations: ['Marítim'],
  });
  assert.equal(editor._child.data.filter_mode, 'exclude');
  assert.equal(editor._child.data.filter_lines, 'L4, 6');
  assert.equal(editor._child.data.filter_destinations, 'Marítim');
  assert.equal(editor._child.computeLabel({ name: 'filter_lines' }), 'Lines Filter (comma-separated, optional)');

  editor._child._listener({
    detail: {
      value: {
        entity: 'sensor.stop',
        max_items: 5,
        title: '',
        filter_mode: 'include',
        filter_lines: '   ',
        filter_destinations: '',
      },
    },
  });
  assert.deepEqual({ ...editor._lastEvent.detail.config }, {
    entity: 'sensor.stop',
    max_items: 5,
  });
});

test('header uses Home Assistant tile info typography with muted secondary text on the right', () => {
  const card = setup();
  setState(card, '13:05', { friendly_name: 'EMT 1330: Quartell', departures: [future] });
  const html = card.shadowRoot.innerHTML;
  assert.match(html, /\.card-header\s*\{[^}]*align-items:\s*center;[^}]*justify-content:\s*space-between;/);
  assert.match(html, /\.status-meta\s*\{[^}]*flex-shrink:\s*0;[^}]*white-space:\s*nowrap;/);
  assert.match(html, /--ha-tile-info-primary-font-size,\s*var\(--ha-font-size-m,\s*14px\)/);
  assert.match(html, /--ha-tile-info-primary-font-weight,\s*var\(--ha-font-weight-medium,\s*500\)/);
  assert.match(html, /--ha-tile-info-secondary-font-size,\s*var\(--ha-font-size-s,\s*12px\)/);
  assert.match(html, /--ha-tile-info-secondary-line-height,\s*var\(--ha-line-height-condensed,\s*16px\)/);
  assert.match(html, /--ha-tile-info-secondary-color,\s*var\(--secondary-text-color\)/);
});

test('departures under 5 minutes use the Home Assistant success color', () => {
  const card = setup();
  card.setConfig({ entity: 'sensor.stop', max_items: 10 });
  const fallbackFourMin = new context.Date(now + 4 * 60000);
  const hhmmFour = `${String(fallbackFourMin.getHours()).padStart(2, '0')}:${String(fallbackFourMin.getMinutes()).padStart(2, '0')}`;
  setState(card, '13:05', {
    departures: [
      { line: '1', destination: 'Now stop', time: '13:00', timestamp: '2026-11-13T12:00:00Z' },
      { line: '2', destination: 'Four min stop', time: '13:04', timestamp: '2026-11-13T12:04:00Z' },
      { line: '3', destination: 'Fallback four min', time: hhmmFour },
      { line: '4', destination: 'Five min stop', time: '13:05', timestamp: '2026-11-13T12:05:00Z' },
      { line: '5', destination: 'Far stop', time: '14:30', timestamp: '2026-11-13T13:30:00Z' },
    ],
  });
  const html = card.shadowRoot.innerHTML;
  assert.match(html, /\.time\.soon\s*\{\s*color:\s*var\(--success-color,\s*#43A047\);/);
  assert.match(html, /<span class="time soon">Now<\/span>/);
  assert.equal((html.match(/<span class="time soon">4 min<\/span>/g) || []).length, 2);
  assert.match(html, /<span class="time">5 min<\/span>/);
  assert.match(html, /<span class="time">14:30<\/span>/);
});

test('localizes card and editor in Russian, Spanish, and Valencian with regional and prototype-safe fallbacks', () => {
  const enKeys = Object.keys(context.TRANSLATIONS.en).sort();
  for (const lang of ['ru', 'es', 'ca', 'va']) {
    assert.deepEqual(Object.keys(context.TRANSLATIONS[lang]).sort(), enKeys, `Missing keys for ${lang}`);
  }

  const card = setup();
  const departures = [
    { ...future, line: '4', timestamp: '2026-11-13T12:00:10Z' },
    future,
  ];

  // Russian (including regional tag)
  setState(card, '13:05', { departures }, 'sensor.stop', { language: 'ru-RU' });
  assert.match(card.shadowRoot.innerHTML, />Сейчас</);
  assert.match(card.shadowRoot.innerHTML, />5 мин</);
  assert.match(card.shadowRoot.innerHTML, /30 с назад/);

  // Spanish (regional tag)
  setState(card, '13:05', { departures: [] }, 'sensor.stop', { language: 'es-ES' });
  assert.match(card.shadowRoot.innerHTML, /No hay próximas salidas/);
  assert.match(card.shadowRoot.innerHTML, /hace 30 s/);

  // Valencian (ca, va, ca-valencia)
  for (const lang of ['ca', 'va', 'ca-valencia']) {
    setState(card, '13:05', { departures: [] }, 'sensor.stop', { language: lang });
    assert.match(card.shadowRoot.innerHTML, /No hi ha pròximes eixides/);
    assert.match(card.shadowRoot.innerHTML, /fa 30 s/);
  }

  // Fallback for unknown or prototype keys
  for (const lang of ['de', '__proto__', 'constructor']) {
    setState(card, '13:05', { departures: [] }, 'sensor.stop', { language: lang });
    assert.match(card.shadowRoot.innerHTML, /No upcoming departures/);
  }

  // Editor labels and dropdown options switch dynamically with hass.language
  const editor = new context.Editor();
  editor.setConfig({ entity: 'sensor.stop' });
  editor.hass = { language: 'ru', states: {} };
  assert.equal(editor._child.computeLabel({ name: 'entity' }), 'Сенсор остановки / станции');
  assert.equal(editor._child.schema[3].selector.select.options[0].label, 'Белый список (показывать только совпадения)');

  editor.hass = { language: 'es', states: {} };
  assert.equal(editor._child.computeLabel({ name: 'entity' }), 'Sensor de parada / estación');
  assert.equal(editor._child.schema[3].selector.select.options[1].label, 'Lista negra (ocultar coincidencias)');

  editor.hass = { language: 'va', states: {} };
  assert.equal(editor._child.computeLabel({ name: 'max_items' }), "Màxim d'eixides a mostrar");
  assert.equal(editor._child.schema[3].selector.select.options[0].label, 'Llista blanca (mostra només coincidències)');
});

test('last updated label buckets seconds into 10-second intervals', () => {
  const card = setup();
  const t = context.TRANSLATIONS.en;
  assert.equal(card._formatLastUpdated('2026-11-13T12:00:00Z', t), 'Just now');
  assert.equal(card._formatLastUpdated('2026-11-13T11:59:51Z', t), 'Just now');
  assert.equal(card._formatLastUpdated('2026-11-13T11:59:50Z', t), '10s ago');
  assert.equal(card._formatLastUpdated('2026-11-13T11:59:41Z', t), '10s ago');
  assert.equal(card._formatLastUpdated('2026-11-13T11:59:40Z', t), '20s ago');
  assert.equal(card._formatLastUpdated('2026-11-13T11:59:01Z', t), '50s ago');
  assert.equal(card._formatLastUpdated('2026-11-13T11:59:00Z', t), '1m ago');
});

test('clicking the card opens a modal with all non-expired departures ignoring filters and max_items', () => {
  const card = setup();
  card.setConfig({
    entity: 'sensor.stop',
    title: 'Only Line 4',
    max_items: 1,
    filter_lines: '4',
    filter_destinations: 'empalme',
  });
  setState(card, '13:05', {
    friendly_name: 'FGV 42: Benimaclet',
    departures: [
      { ...future, line: '99', destination: 'Expired stop', timestamp: '2026-11-13T11:59:20Z' },
      ...sampleDepartures,
    ],
  });

  // Closed by default: only the 1 filtered row is rendered on the card
  assert.doesNotMatch(card.shadowRoot.innerHTML, /<dialog class="schedule-dialog"/);
  assert.match(card.shadowRoot.innerHTML, /<ha-ripple><\/ha-ripple>/);
  assert.match(card.shadowRoot.innerHTML, /--ha-ripple-hover-opacity:\s*0\.04/);
  assert.match(card.shadowRoot.innerHTML, /Only Line 4/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /FGV 42: Benimaclet/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /Dr\. Lluch|Marítim|Palau de Congressos|Estació del Nord/);

  // Simulate clicking the interactive card
  card._onShadowClick({
    target: {
      closest(selector) {
        return selector === 'ha-card.interactive' ? {} : null;
      },
    },
  });

  assert.equal(card._dialogOpen, true);
  assert.equal(card.getCardSize(), 3); // Card size remains based on the 1 filtered row
  const html = card.shadowRoot.innerHTML;
  assert.match(html, /<dialog class="schedule-dialog" open/);
  assert.match(html, /class="dialog-title"[^>]*>FGV 42: Benimaclet<\/div>/);
  // All 5 non-expired departures appear in the modal, but not the expired one
  assert.match(html, /Empalme/);
  assert.match(html, /Dr\. Lluch/);
  assert.match(html, /Marítim/);
  assert.match(html, /Palau de Congressos/);
  assert.match(html, /Estació del Nord/);
  assert.doesNotMatch(html, /Expired stop/);
});

test('modal more-info button closes the modal and dispatches hass-more-info for the sensor entity', () => {
  const card = setup();
  setState(card, '13:05', { friendly_name: 'EMT 1330: Quartell', departures: [future] });
  card._openDialog();
  assert.equal(card._dialogOpen, true);

  card._onShadowClick({
    stopPropagation() {},
    target: {
      closest(selector) {
        return selector === '.dialog-more-info' ? {} : null;
      },
    },
  });

  assert.equal(card._dialogOpen, false);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /<dialog class="schedule-dialog"/);
  assert.equal(card._lastEvent.type, 'hass-more-info');
  assert.deepEqual({ ...card._lastEvent.detail }, { entityId: 'sensor.stop' });
});

test('modal closes on close button, backdrop click, Escape key, entity change, and placeholder state', () => {
  const card = setup();
  setState(card, '13:05', { friendly_name: 'EMT 1330: Quartell', departures: [future] });

  // Open via Enter key on interactive card
  card._onShadowKeyDown({
    key: 'Enter',
    preventDefault() {},
    target: {
      closest(selector) {
        return selector === 'ha-card.interactive' ? {} : null;
      },
    },
  });
  assert.equal(card._dialogOpen, true);

  // Close via close button
  card._onShadowClick({
    stopPropagation() {},
    target: {
      closest(selector) {
        return selector === '.dialog-close' ? {} : null;
      },
    },
  });
  assert.equal(card._dialogOpen, false);

  // Reopen and close via backdrop click (target === dialog)
  card._openDialog();
  const dialogNode = {
    closest(selector) {
      return selector === '.schedule-dialog' ? dialogNode : null;
    },
  };
  card._onShadowClick({ target: dialogNode });
  assert.equal(card._dialogOpen, false);

  // Reopen and close via Escape key
  card._openDialog();
  card._onShadowKeyDown({ key: 'Escape', preventDefault() {} });
  assert.equal(card._dialogOpen, false);

  // Reopen and verify switching entity closes modal and placeholder cannot open modal
  card._openDialog();
  card.setConfig({ entity: 'sensor.other' });
  assert.equal(card._dialogOpen, false);
  card._openDialog();
  assert.equal(card._dialogOpen, false);
});
