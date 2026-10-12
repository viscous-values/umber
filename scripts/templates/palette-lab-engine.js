// Umber Palette Lab — color engine.
//
// A line-for-line port of scripts/palette_lib.py (role merge + resolve) and
// scripts/palette_audit.py (color math + check evaluation), so the lab can
// re-audit live while you tune. tests/test_palette_lab.py runs this file
// under node and requires it to match the Python numbers for every check.
// render_lab.py inlines it into mockups/palette-lab.html.

const Engine = (() => {
  const HEX_RE = /^#[0-9A-F]{6}$/;

  // ------------------------------------------------------------ color math
  function hexRgb(h) {
    const s = h.replace('#', '');
    return [0, 2, 4].map(i => parseInt(s.slice(i, i + 2), 16));
  }
  function rgbHex(rgb) {
    return '#' + rgb.map(c => Math.max(0, Math.min(255, Math.round(c)))
      .toString(16).toUpperCase().padStart(2, '0')).join('');
  }
  function toLinear(c8) {
    const c = c8 / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  }
  function toSrgb8(lin) {
    lin = Math.max(0, Math.min(1, lin));
    const c = lin <= 0.0031308 ? 12.92 * lin : 1.055 * lin ** (1 / 2.4) - 0.055;
    return c * 255;
  }
  function oklab(h) {
    const [r, g, b] = hexRgb(h).map(toLinear);
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    return [
      0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
      1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
      0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    ];
  }
  function oklch(h) {
    const [L, a, b] = oklab(h);
    const hue = ((Math.atan2(b, a) * 180 / Math.PI) % 360 + 360) % 360;
    return [L, Math.hypot(a, b), hue];
  }
  // OKLCH -> hex, clipping to sRGB. inGamut is false when clipping moved a channel.
  function oklchToHex(L, C, h) {
    const a = C * Math.cos(h * Math.PI / 180), b = C * Math.sin(h * Math.PI / 180);
    const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
    const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
    const s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3;
    const lin = [
      4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    ];
    const inGamut = lin.every(c => c >= -0.001 && c <= 1.001);
    return { hex: rgbHex(lin.map(toSrgb8)), inGamut };
  }
  function deltaE(x, y) {
    const [a, b] = [oklab(x), oklab(y)];
    return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  }
  const ACHROMATIC_C = 0.02;  // below this chroma a color has no meaningful hue
  function hueDelta(x, y) {
    const [, cx, hx] = oklch(x), [, cy, hy] = oklch(y);
    if (Math.min(cx, cy) < ACHROMATIC_C) return 0;
    const d = Math.abs(hx - hy) % 360;
    return Math.min(d, 360 - d);
  }
  function luminance(h) {
    const [r, g, b] = hexRgb(h).map(toLinear);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  function contrast(x, y) {
    const [hi, lo] = [luminance(x), luminance(y)].sort((p, q) => q - p);
    return (hi + 0.05) / (lo + 0.05);
  }
  function apca(text, bg) {
    const y = h => {
      const [r, g, b] = hexRgb(h).map(c => (c / 255) ** 2.4);
      const v = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b;
      return v < 0.022 ? v + (0.022 - v) ** 1.414 : v;
    };
    const yt = y(text), yb = y(bg);
    if (Math.abs(yb - yt) < 0.0005) return 0;
    if (yb > yt) {
      const sapc = (yb ** 0.56 - yt ** 0.57) * 1.14;
      return sapc < 0.1 ? 0 : (sapc - 0.027) * 100;
    }
    const sapc = (yb ** 0.65 - yt ** 0.62) * 1.14;
    return sapc > -0.1 ? 0 : (sapc + 0.027) * 100;
  }
  // Machado, Oliveira & Fernandes 2009, severity 1.0, applied in linear RGB.
  const CVD = {
    protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    tritan: [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
  };
  function simulateCvd(h, kind) {
    const lin = hexRgb(h).map(toLinear);
    return rgbHex(CVD[kind].map(row => toSrgb8(row[0] * lin[0] + row[1] * lin[1] + row[2] * lin[2])));
  }
  // Grey of equal OKLab lightness — the "value only" view.
  function toGrey(h) {
    return oklchToHex(oklch(h)[0], 0, 0).hex;
  }

  // ------------------------------------------------------------ roles
  const isTable = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  function deepMerge(defaults, overrides, path = 'role') {
    const merged = structuredClone(defaults);
    for (const [key, val] of Object.entries(overrides || {})) {
      const where = `${path}.${key}`;
      if (!(key in merged)) throw new Error(`unknown role override: ${where}`);
      if (isTable(merged[key]) !== isTable(val)) throw new Error(`role override ${where}: table/value mismatch`);
      merged[key] = isTable(val) ? deepMerge(merged[key], val, where) : val;
    }
    return merged;
  }
  function resolve(pal, key, chain = []) {
    if (chain.includes(key)) throw new Error('role cycle: ' + [...chain, key].join(' -> '));
    let val = pal;
    for (const part of key.split('.')) {
      if (!isTable(val) || !(part in val)) throw new Error('unresolvable key: ' + [...chain, key].join(' -> '));
      val = val[part];
    }
    if (key.startsWith('var.')) return val;
    if (typeof val !== 'string') throw new Error(`${key} is a table, not a color`);
    if (val.startsWith('#')) {
      if (!HEX_RE.test(val)) throw new Error(`${key} = '${val}': colors must be uppercase #RRGGBB`);
      return val;
    }
    return resolve(pal, val, [...chain, key]);
  }
  function resolveTree(pal, table, prefix) {
    for (const [key, val] of Object.entries(table)) {
      const full = `${prefix}.${key}`;
      if (isTable(val)) resolveTree(pal, val, full);
      else table[key] = resolve(pal, full);
    }
  }
  // variant: {tiers: {hearth: {...}, ...}, role: {overrides}}; roles: roles.toml [role] tree.
  function prepare(variant, roles) {
    const pal = structuredClone(variant.tiers);
    pal.role = deepMerge(roles, variant.role || {});
    resolveTree(pal, pal.role, 'role');
    return pal;
  }
  const role = (pal, key) => resolve(pal, 'role.' + key);

  // ------------------------------------------------------------ checks
  function measure(kind, a, b, cvd) {
    switch (kind) {
      case 'contrast': return contrast(a, b);
      case 'dl': return oklch(b)[0] - oklch(a)[0];
      case 'de': return deltaE(a, b);
      case 'dh': return hueDelta(a, b);
      case 'cvd': return deltaE(simulateCvd(a, cvd), simulateCvd(b, cvd));
      case 'apca': return Math.abs(apca(a, b));
      default: throw new Error(`unknown check kind ${kind}`);
    }
  }
  const passes = (value, op, threshold) => (op === '>=' ? value >= threshold : value <= threshold);
  function evaluate(spec, pal) {
    const value = measure(spec.kind, role(pal, spec.a), role(pal, spec.b), spec.cvd);
    return { ...spec, value, ok: passes(value, spec.op, spec.threshold) };
  }
  function auditVariant(pal, specs) {
    return specs.map(s => evaluate(s, pal));
  }
  // entries: [{slug, pal}]; familySpecs from palette_audit.family_specs().
  function auditFamily(entries, familySpecs) {
    const out = [];
    for (let i = 0; i < entries.length; i++) {
      for (let j = i + 1; j < entries.length; j++) {
        const [A, B] = [entries[i], entries[j]];
        for (const spec of familySpecs) {
          const value = spec.roles.reduce((sum, k) => sum + deltaE(role(A.pal, k), role(B.pal, k)), 0) / spec.roles.length;
          out.push({ id: `${spec.id}:${A.slug}~${B.slug}`, group: 'cross', kind: 'de', a: A.slug, b: B.slug,
                     op: '>=', threshold: spec.threshold, level: 'error', value, ok: value >= spec.threshold });
        }
      }
    }
    return out;
  }

  // ------------------------------------------------------------ tuner edits
  // Saved edits are {"tier.key": {from, to}}. An edit applies only while the
  // palette file still holds `from`; once the file changes underneath it the
  // edit is stale and dropped, so regenerated drafts are never shadowed.
  function diffEdits(original, tuned) {
    const edits = {};
    for (const [tier, colors] of Object.entries(tuned))
      for (const [k, hex] of Object.entries(colors))
        if (original[tier]?.[k] !== hex) edits[`${tier}.${k}`] = { from: original[tier]?.[k], to: hex };
    return edits;
  }
  function applyEdits(tiers, edits) {
    const out = structuredClone(tiers), applied = [], stale = [];
    for (const [key, { from, to }] of Object.entries(edits || {})) {
      const dot = key.indexOf('.'), tier = key.slice(0, dot), k = key.slice(dot + 1);
      if (out[tier]?.[k] !== undefined && out[tier][k] === from) { out[tier][k] = to; applied.push(key); }
      else stale.push(key);
    }
    return { tiers: out, applied, stale };
  }

  // ------------------------------------------------------------ TOML export
  const tomlKey = k => (/^[A-Za-z_][\w-]*$/.test(k) ? k : JSON.stringify(k));
  const tomlVal = x => (typeof x === 'string' ? JSON.stringify(x) : String(x));
  // A complete palette file: [meta], every tier (with OKLCH notes), [role] overrides.
  function toToml(v) {
    let out = `# ${v.name} — exported from the Umber Palette Lab\n`;
    if (v.meta && Object.keys(v.meta).length)
      out += '\n[meta]\n' + Object.entries(v.meta).map(([k, x]) => `${tomlKey(k)} = ${tomlVal(x)}`).join('\n') + '\n';
    for (const [tier, colors] of Object.entries(v.tiers)) {
      out += `\n[${tier}]\n` + Object.entries(colors).map(([k, hex]) => {
        const [L, C, H] = oklch(hex);
        return `${tomlKey(k).padEnd(18)} = "${hex}"   # L ${L.toFixed(3)} C ${C.toFixed(3)} h ${H.toFixed(0)}`;
      }).join('\n') + '\n';
    }
    const emit = (obj, path) => {
      const scalars = Object.entries(obj).filter(([, x]) => !isTable(x));
      const tables = Object.entries(obj).filter(([, x]) => isTable(x));
      let s = scalars.length ? `\n[${path}]\n` + scalars.map(([k, x]) => `${tomlKey(k)} = ${tomlVal(x)}`).join('\n') + '\n' : '';
      for (const [k, x] of tables) s += emit(x, `${path}.${tomlKey(k)}`);
      return s;
    };
    if (v.role && Object.keys(v.role).length) out += emit(v.role, 'role');
    return out;
  }

  return { hexRgb, rgbHex, oklab, oklch, oklchToHex, deltaE, hueDelta, luminance, contrast, apca,
           simulateCvd, toGrey, deepMerge, resolve, prepare, role, measure, evaluate, auditVariant, auditFamily,
           diffEdits, applyEdits, toToml };
})();

if (typeof module !== 'undefined') module.exports = Engine;
