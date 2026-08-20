/* OKAWARI 門頭屏 · 模擬器共用邏輯
   ================================================================
   兩頁共用：screen.html（屏長什麼樣）與 console.html（後台按什麼）。

   為什麼要有模擬器：卡還沒上牆、按鈕還沒買，但故事線要先跟業主定案。
   這一套在瀏覽器裡把「時段自己換」「客人按續飯」「店員按滿額」
   全部跑一遍，不需要任何硬體。

   兩頁怎麼講話：BroadcastChannel（同一台機器、同一個瀏覽器）。
   ★ 這是模擬用的，不是真的通訊架構 —— 真機是後台送 SwitchProgram 給卡。
     跨裝置（例如 iPad 當按鈕）BroadcastChannel 是打不通的，
     那要走真的後台伺服器。這件事在 console 上有標出來。
   ================================================================ */

const CH = 'okawari-sim';
const LS = 'okawari-sim-state';

/* 四段常駐。時段跟 stores.json 的 contents[].when 是同一組，
   改這裡要記得兩邊一起改 —— 模擬跟真機對不上就失去意義了。 */
export const SEGMENTS = [
  { key: 'opening', name: '開店畫面',        from: '11:00', to: '11:30', secs: 14 },
  { key: 'noon',    name: '今天也要好好吃飯',  from: '11:30', to: '14:00', secs: 16 },
  { key: 'siesta',  name: '午後發呆 Zzz',     from: '14:00', to: '17:30', secs: 20 },
  { key: 'evening', name: '今天辛苦了，吃飯吧', from: '17:30', to: '22:30', secs: 16 },
];

export const EVENTS = {
  combo1: { name: '續飯 COMBO 1',  secs: 3,  who: '客人' },
  combo2: { name: '續飯 COMBO 2',  secs: 4,  who: '客人' },
  combo3: { name: '續飯 COMBO 3',  secs: 7,  who: '客人' },
  bonus:  { name: '滿額 1000',     secs: 9,  who: '店員' },
  bogo:   { name: '買一送一',      secs: 13, who: '活動' },
};

/* 門店。畫布比例不同，屏的長寬比會差 8%，模擬要看得出來。 */
export const STORES = [
  { id: 'taichung', name: '新光三越台中港', w: 1040, h: 120 },
  { id: 'tainan',   name: '新光三越台南小北', w: 960,  h: 120 },
];

export const OPEN_AT = '11:00', CLOSE_AT = '22:30';

/* COMBO 多久沒人按就歸零。真機也要設同一個數字 ——
   不歸零的話今天第 3 位客人按下去會直接跳 COMBO 3。 */
export const COMBO_RESET_MS = 30000;

const DEFAULTS = {
  character: 'ricebowl',
  store: 'tainan',
  latency: 400,        // 模擬 SwitchProgram 來回要幾毫秒
  clockMode: 'real',   // real | fixed
  fixedMin: 12 * 60,   // clockMode=fixed 時停在哪一分
  combo: 0,
  comboAt: 0,
};

export function hhmm(min) {
  return String(Math.floor(min / 60)).padStart(2, '0') + ':' +
         String(min % 60).padStart(2, '0');
}

export function toMin(s) {
  const [h, m] = s.split(':').map(Number);
  return h * 60 + m;
}

export function loadState() {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(LS) || '{}') }; }
  catch (e) { return { ...DEFAULTS }; }
}

export function saveState(s) {
  try { localStorage.setItem(LS, JSON.stringify(s)); } catch (e) {}
}

/* 現在幾點（分鐘）。fixed 模式是為了不用等到晚上七點才看得到晚間那段。 */
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

/* ---------------------------------------------------------------- 訊息 */
export function bus() {
  const ch = new BroadcastChannel(CH);
  return {
    send(type, data) { ch.postMessage({ type, data, at: Date.now() }); },
    on(fn) { ch.onmessage = e => fn(e.data.type, e.data.data); },
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
