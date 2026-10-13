// PvZ Horror Edition - live English translator (injected by the launcher with Frida).
// Host injects: DICT = {exact, patterns, terms, templates}, FP = {name: {rva, bytes}}, OPTS = {mt: bool}
'use strict';
const CJK = /[㐀-鿿＀-￯　-〿]/;
const exact = new Map(Object.entries(DICT.exact));
const templates = new Map(Object.entries(DICT.templates || {}));
const patterns = DICT.patterns.map(([re, rep]) => [new RegExp('^' + re + '$', 's'), rep]);
const terms = Object.entries(DICT.terms)
  .concat(Object.entries(DICT.exact).filter(([zh]) => zh.length >= 4))
  .sort((a, b) => b[0].length - a[0].length);
const cache = new Map();
const seen = new Set();
let STRING_KLASS = null;
let fastAlloc = null;

function toTemplate(s) {
  const nums = [];
  const t = s.replace(/\d+(?:\.\d+)?/g, m => { nums.push(m); return '{' + nums.length + '}'; });
  return [t, nums];
}
function fromTemplate(t, nums) { return t.replace(/\{(\d+)\}/g, (m, i) => (nums[i - 1] !== undefined ? nums[i - 1] : m)); }

function machine(tpl) {
  send({ type: 'mt', text: tpl });
  let res = null;
  recv('mt', m => { res = m.text; }).wait();
  return res;
}

function translate(s) {
  const hit = cache.get(s);
  if (hit !== undefined) return hit;
  let out = exact.get(s);
  if (out === undefined) for (const [re, rep] of patterns) if (re.test(s)) { out = s.replace(re, rep); break; }
  const [tpl, nums] = toTemplate(s);
  if (out === undefined && templates.has(tpl)) out = fromTemplate(templates.get(tpl), nums);
  if (out === undefined) {
    let t = s;
    for (const [zh, en] of terms) if (t.includes(zh)) t = t.split(zh).join(en);
    if (!CJK.test(t)) out = t;
  }
  if (out === undefined && OPTS.mt) {
    const r = machine(tpl);
    if (r) { templates.set(tpl, r); out = fromTemplate(r, nums); }
  }
  if (out === undefined) {
    out = s;
    send({ type: 'untranslated', text: s });
  }
  if (cache.size < 50000) cache.set(s, out);
  return out;
}

function readStr(p) {
  const len = p.add(0x10).readS32();
  if (len <= 0 || len > 200000) return null;
  return p.add(0x14).readUtf16String(len);
}
function newStr(s) {
  const p = fastAlloc(s.length, ptr(0));
  if (p.isNull()) return null;
  p.add(0x14).writeUtf16String(s);
  return p;
}
function isManagedString(p) {
  if (p.isNull() || STRING_KLASS === null) return false;
  try { return p.readPointer().equals(STRING_KLASS); } catch (e) { return false; }
}

function replaceArg(args, i, label) {
  try {
    const p = args[i];
    if (p.isNull()) return;
    const s = readStr(p);
    if (s === null || !CJK.test(s)) return;
    const t = translate(s);
    if (OPTS.debug) send({ type: 'dbg', where: label, from: s.slice(0, 80), to: t.slice(0, 80) });
    if (t !== s) { const n = newStr(t); if (n) args[i] = n; }
  } catch (e) { send({ type: 'error', where: label, msg: String(e) }); }
}

function install(ga) {
  const base = ga.base;
  const bad = [];
  for (const [name, f] of Object.entries(FP)) {
    const got = Array.from(new Uint8Array(base.add(parseInt(f.rva)).readByteArray(16))).map(b => b.toString(16).padStart(2, '0')).join('');
    if (got !== f.bytes) bad.push(name);
  }
  if (bad.length) { send({ type: 'fatal', msg: 'Unsupported game version (code mismatch: ' + bad.join(', ') + ')' }); return; }
  const at = name => base.add(parseInt(FP[name].rva));
  fastAlloc = new NativeFunction(at('fastAlloc'), 'pointer', ['int', 'pointer']);

  // text property setters: the argument is always a string -> learn the String class pointer from it
  const skip = new Set(OPTS.skip || []);
  for (const name of ['tmpSetText', 'uiSetText'].filter(n => !skip.has(n))) {
    Interceptor.attach(at(name), {
      onEnter(args) {
        if (STRING_KLASS === null && !args[1].isNull()) STRING_KLASS = args[1].readPointer();
        replaceArg(args, 1, name);
      }
    });
  }
  // SetText overloads: only touch the argument when it really is a managed string
  for (const name of ['setText1a', 'setText1b', 'setText2a', 'setText2b', 'setText3a', 'setText3b'].filter(n => !skip.has(n))) {
    Interceptor.attach(at(name), { onEnter(args) { if (isManagedString(args[1])) replaceArg(args, 1, name); } });
  }
  // log every Chinese string the obfuscator decrypts (for building the dictionary; nothing is changed here)
  if (!skip.has('decryptRvaString')) Interceptor.attach(at('decryptRvaString'), {
    onLeave(ret) {
      try {
        if (ret.isNull()) return;
        const s = readStr(ret);
        if (s && CJK.test(s) && !seen.has(s)) { seen.add(s); send({ type: 'seen', text: s }); }
      } catch (e) {}
    }
  });
  send({ type: 'ready' });
}

(function waitForGame() {
  const ga = Process.findModuleByName('GameAssembly.dll');
  if (ga) { setTimeout(() => install(ga), 500); return; }
  setTimeout(waitForGame, 100);
})();
