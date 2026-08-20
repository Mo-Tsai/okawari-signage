/* OKAWARI 門頭屏 · 模擬層共用邏輯
   ================================================================
   架構（2026-08-19 業主定的，跟第一版不同，這裡記下來免得又走偏）：

     後台       console.html            三家店的總覽，看狀態
                store.html?id=…         單店設定。三個區塊 = 三頁
     店端       screen.html?id=…        那家店的屏 + 那家店的按鈕

   兩件事要分清楚：

   1. **後台是設定與監看的地方，不是按按鈕的地方。**
      後台要能看每一家店現在什麼狀況，設定也在後台各店的頁面上做。
      未來這三頁的內容往上累加，就是總部的多店後台。

   2. **COMBO 做在各端，不在後台。**
      客人續飯是在店裡按的，店員滿額也是在店裡按的 ——
      按鈕接在店內那台小主機上，訊號不會繞去總部再回來。
      所以觸發鈕長在 screen.html（店端）上，後台頁上沒有。

   三個端：台中港店、台南小北店、測試屏（放在台南總部）。

   ---------------------------------------------------------------
   兩頁怎麼講話：BroadcastChannel（同一台機器、同一個瀏覽器）。
   ★ 這是模擬用的，不是真的通訊架構 —— 真機是各店的小主機對自己那張卡
     送 SwitchProgram，總部只負責推內容跟收心跳。
   ================================================================ */

const CH = 'okawari-sim';
const LS = 'okawari-sim-v2';

/* 四段常駐。時段跟 stores.json 的 contents[].when 是同一組，
   改這裡要記得兩邊一起改 —— 模擬跟真機對不上就失去意義了。 */
export const SEGMENTS = [
  { key: 'opening', name: '開店畫面',        from: '11:00', to: '11:30', secs: 14 },
  { key: 'noon',    name: '今天也要好好吃飯',  from: '11:30', to: '14:00', secs: 16 },
  { key: 'siesta',  name: '午後發呆 Zzz',     from: '14:00', to: '17:30', secs: 20 },
  { key: 'evening', name: '今天辛苦了，吃飯吧', from: '17:30', to: '22:30', secs: 16 },
];

export const EVENTS = {
  combo1: { name: '續飯 COMBO 1', secs: 3,  who: '客人' },
  combo2: { name: '續飯 COMBO 2', secs: 4,  who: '客人' },
  combo3: { name: '續飯 COMBO 3', secs: 7,  who: '客人' },
  bonus:  { name: '滿額 1000',    secs: 9,  who: '店員' },
  bogo:   { name: '買一送一',     secs: 13, who: '活動' },
};

/* 三個端。畫布尺寸取自 stores.json，不要在這裡自己編。
   測試屏是台南等比縮 1/3 之後取中間那段 —— 所以它不是獨立設計，
   而是「台南那面屏的一個視窗」。模擬要照這個演，不然測試屏上看到的
   跟門市不是同一個比例，測了也不算數。 */
export const STORES = [
  { id: 'taichung', name: '新光三越台中港', short: '台中屏',
    w: 1040, h: 120, where: '門市' },
  { id: 'tainan', name: '新光三越台南小北', short: '台南屏',
    w: 960, h: 120, where: '門市' },
  { id: 'test', name: '測試屏（台南總部）', short: '測試屏',
    w: 160, h: 40, where: '總部', mirrorOf: 'tainan', mirrorZoom: 2 },
];

export const OPEN_AT = '11:00', CLOSE_AT = '22:30';

/* COMBO 多久沒人按就歸零。真機也要設同一個數字 ——
   不歸零的話今天第 3 位客人按下去會直接跳 COMBO 3。 */
export const COMBO_RESET_MS = 30000;

const STORE_DEFAULTS = {
  character: 'ricebowl',
  latency: 400,          // 模擬 SwitchProgram 來回要幾毫秒
  clockMode: 'real',     // real | fixed
  fixedMin: 12 * 60,
  bogoText: '1 + 1',
  bogoDate: '9/1-9/2',
  bonusText: 'GOLDEN BOWL UNLOCKED!',
  eveningText: '',
  combo: 0,
  comboAt: 0,
  lastEvent: '',
  lastEventAt: 0,
};

/* 各店檔期不同，預設值也要不同 —— 一開就是對的，比較不會被漏改。 */
const STORE_SEED = {
  taichung: { bogoDate: '9/1-9/2' },
  tainan:   { bogoDate: '9/2-9/3' },
  test:     { bogoDate: '9/1-9/2', latency: 200 },
};

export function storeById(id) {
  return STORES.find(s => s.id === id) || STORES[1];
}

export function hhmm(min) {
  return String(Math.floor(min / 60)).padStart(2, '0') + ':' +
         String(min % 60).padStart(2, '0');
}

export function toMin(s) {
  const [h, m] = s.split(':').map(Number);
  return h * 60 + m;
}

/* ---------------------------------------------------------------- 狀態
   每一家店有自己的一份。第一版是所有店共用一份，那是錯的 ——
   後台要看的就是「各店各自什麼狀況」。 */
function readAll() {
  let raw = {};
  try { raw = JSON.parse(localStorage.getItem(LS) || '{}'); } catch (e) {}
  const out = {};
  for (const s of STORES) {
    out[s.id] = { ...STORE_DEFAULTS, ...(STORE_SEED[s.id] || {}), ...(raw[s.id] || {}) };
  }
  return out;
}

export function loadStore(id) { return readAll()[id] || { ...STORE_DEFAULTS }; }
export function loadAll() { return readAll(); }

export function saveStore(id, st) {
  const all = readAll();
  all[id] = st;
  try { localStorage.setItem(LS, JSON.stringify(all)); } catch (e) {}
}

export function nowMin(st) {
  if (st.clockMode === 'fixed') return st.fixedMin;
  const d = new Date();
  return d.getHours() * 60 + d.getMinutes();
}

/* 這個時間該播哪一段。回 null = 打烊，屏是關的。 */
export function segmentAt(min) {
  if (min < toMin(OPEN_AT) || min >= toMin(CLOSE_AT)) return null;
  return SEGMENTS.find(s => min >= toMin(s.from) && min < toMin(s.to)) || null;
}

export function videoSrc(key, character) {
  return `preview/${key}_${character}.mp4`;
}

/* ---------------------------------------------------------------- 訊息
   每一則都帶 store id。沒有 id 的訊息會讓三個端一起動，
   那就變回第一版那個「全部共用一份」的錯誤了。 */
export function bus() {
  const ch = new BroadcastChannel(CH);
  return {
    send(type, id, data) { ch.postMessage({ type, id, data, at: Date.now() }); },
    on(fn) { ch.onmessage = e => fn(e.data.type, e.data.id, e.data.data); },
  };
}

/* 按一次續飯按鈕 → 現在是第幾次。
   超過 COMBO_RESET_MS 沒人按就從頭算；第三次之後歸零，下一位客人重新開始。 */
export function bumpCombo(st) {
  const now = Date.now();
  let n = (now - st.comboAt > COMBO_RESET_MS) ? 0 : st.combo;
  n = n >= 3 ? 1 : n + 1;
  st.combo = n;
  st.comboAt = now;
  return n;
}

/* 影片自己播。autoplay muted 本身有效，但分頁切到背景時
   瀏覽器會暫停省電，回到前景不一定自己續播。
   所以每次 tick 補踢一下，切回來就會繼續動。 */
export function keepPlaying(root = document) {
  const kick = () => root.querySelectorAll('video')
    .forEach(v => v.play().catch(() => {}));
  addEventListener('load', kick);
  addEventListener('pointerdown', kick, { once: true });
  setTimeout(kick, 300);
  return kick;
}
