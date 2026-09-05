
let k = (fn) => { fn(); return fn; };
let u2e = () => {};
let vA = () => {};
let iR = {};

function AWs(e, t) {
  const s = e.charCodeAt(t);
  if (s === 36)
    return e.charCodeAt(t + 1) === 36 ? "$$" : "$";
  if (s !== 92)
    return;
  const o = e.charCodeAt(t + 1);
  if (o === 40)
    return "\\(";
  if (o === 91)
    return "\\[";
  return;
}
function IWs(e, t, s) {
  let o = 0;
  for (let n = t - 1;n >= s && e.charCodeAt(n) === 92; n--)
    o++;
  return o % 2 === 1;
}
function Bpr(e, t, s) {
  const o = t === "\\(" ? "\\)" : t === "\\[" ? "\\]" : t;
  for (let n = e.indexOf(o, s);n !== -1; n = e.indexOf(o, n + 1)) {
    if (!IWs(e, n, s))
      return n;
  }
  return -1;
}
function Kpr(e, t) {
  const s = e[t + 1];
  if (s === undefined || s === " " || s === "\t" || s === "\n" || s === "$")
    return -1;
  for (let o = t + 1;o < e.length; o++) {
    const n = e[o];
    if (n === "\\") {
      o++;
      continue;
    }
    if (n === "\n")
      return -1;
    if (n !== "$")
      continue;
    const r = e[o - 1];
    if (r === " " || r === "\t")
      return -1;
    const i = e[o + 1];
    if (i !== undefined && i >= "0" && i <= "9")
      continue;
    return e.slice(t + 1, o).trim().length > 0 ? o : -1;
  }
  return -1;
}
function KJ(e, t, s = 0) {
  const o = AWs(e, t);
  if (o === undefined || IWs(e, t, s))
    return;
  const n = t + o.length;
  const r = o === "$" ? Kpr(e, t) : Bpr(e, o, n);
  if (r === -1)
    return;
  const i = e.slice(n, r);
  if (o === "$$" && i.trim() === "")
    return;
  return { opener: o, display: o === "$$" || o === "\\[", end: r + o.length, body: i };
}
// packages/tui/src/latex-to-unicode.ts
function Nmo(e, t, s) {
  return { bold: e.bold, italic: e.italic, foreground: t, background: s };
}
function Kmo(e, t) {
  return e.bold === t.bold && e.italic === t.italic && e.foreground === t.foreground && e.background === t.background;
}
function eve(e, t) {
  for (const s of t) {
    if (s.text === "")
      continue;
    const o = e[e.length - 1];
    if (o !== undefined && o.after === undefined && s.before === undefined && s.after === undefined && Kmo(o.style, s.style)) {
      o.text += s.text;
    } else {
      e.push({ ...s });
    }
  }
}
function yw(...e) {
  const t = [];
  for (const s of e)
    eve(t, s);
  return t;
}
function $o(e, t) {
  return e === "" ? [] : [{ text: e, style: t }];
}
function vYe(e) {
  let t = "";
  for (const s of e)
    t += s.text;
  return t;
}
function Hmo(e, t) {
  const s = [];
  for (const o of e) {
    let n = "";
    for (const r of o.text) {
      const i = t[r];
      if (i === undefined)
        return null;
      n += i;
    }
    eve(s, [{ ...o, text: n }]);
  }
  return s;
}
function J2t(e) {
  let t = 0;
  for (const s of e) {
    for (const o of s.text)
      t++;
  }
  return t;
}
function gpi(e, t) {
  const s = dpi[`${t}:${e}`];
  if (s)
    return s;
  const o = cpi[t];
  const n = e.charCodeAt(0);
  if (n >= 65 && n <= 90)
    return String.fromCodePoint(o.upper + (n - 65));
  if (n >= 97 && n <= 122)
    return String.fromCodePoint(o.lower + (n - 97));
  if (n >= 48 && n <= 57 && o.digit !== undefined)
    return String.fromCodePoint(o.digit + (n - 48));
  return e;
}
function eBt(e, t) {
  if (t.font === null)
    return e;
  const s = e.charCodeAt(0);
  const o = s >= 65 && s <= 90 || s >= 97 && s <= 122 || s >= 48 && s <= 57;
  return o ? gpi(e, t.font) : e;
}
function uR(e, t, s, o) {
  return yw($o(t, o), e, $o(s, o));
}
function mpi(e) {
  const t = e.map((s) => ({ ...s }));
  while (t.length > 0) {
    const s = t[0];
    if (s === undefined)
      break;
    s.text = s.text.trimStart();
    if (s.text !== "")
      break;
    t.shift();
  }
  while (t.length > 0) {
    const s = t.length - 1;
    const o = t[s];
    if (o === undefined)
      break;
    o.text = o.text.trimEnd();
    if (o.text !== "")
      break;
    t.pop();
  }
  return t;
}
function hpi(e, t, s) {
  if (!s || e.length === 0)
    return e;
  const o = e.map((i) => ({ ...i }));
  const n = o[0];
  const r = o[o.length - 1];
  if (n?.style[t]) {
    n.before = [...n.before ?? [], { kind: "scope-start", attribute: t }];
  }
  if (r?.style[t]) {
    r.after = [...r.after ?? [], { kind: "scope-end", attribute: t, restore: true }];
  }
  return o;
}
function Vj(e, t) {
  const s = [];
  for (const o of e) {
    let n = "";
    for (const r of o.text)
      n += r === " " ? r : r + t;
    eve(s, [{ ...o, text: n }]);
  }
  return s;
}
function Wmo(e, t, s) {
  if (t.bold && !s.bold)
    e.push(zmo);
  if (t.italic && !s.italic)
    e.push(Bmo);
  const o = t.foreground !== s.foreground;
  const n = t.background !== s.background;
  if (o && n) {
    if (s.background === null) {
      e.push(s.background ?? Q2t);
      e.push(s.foreground ?? JSe);
    } else {
      e.push(s.foreground ?? JSe);
      e.push(s.background ?? Q2t);
    }
  } else {
    if (o)
      e.push(s.foreground ?? JSe);
    if (n)
      e.push(s.background ?? Q2t);
  }
  if (!t.bold && s.bold)
    e.push(sBt);
  if (!t.italic && s.italic)
    e.push(oBt);
}
function Lmo(e, t, s) {
  if (t.kind === "scope-start") {
    e.push(t.attribute === "bold" ? sBt : oBt);
    return { ...s, [t.attribute]: true };
  }
  if (s[t.attribute])
    e.push(t.attribute === "bold" ? zmo : Bmo);
  if (t.restore)
    e.push(t.attribute === "bold" ? sBt : oBt);
  return { ...s, [t.attribute]: t.restore };
}
function ypi(e) {
  let t = "";
  let s = qmo;
  for (const n of e) {
    const r = [];
    Wmo(r, s, n.style);
    t += r.join("");
    s = n.style;
    for (const i of n.before ?? []) {
      const a = [];
      s = Lmo(a, i, s);
      t += a.join("");
    }
    t += n.text;
    for (const i of n.after ?? []) {
      const a = [];
      s = Lmo(a, i, s);
      t += a.join("");
    }
  }
  const o = [];
  Wmo(o, s, qmo);
  return t + o.join("");
}
function QSe(e) {
  return e.replace(/\\([&%$#_{}\s])/g, "$1").replace(/~/g, " ");
}
function Tpi() {
  return bt.trueColor ? "ansi-16m" : "ansi-256";
}
function ME(e) {
  if (e <= 0)
    return 0;
  if (e >= 1)
    return 1;
  return e;
}
function tBt(e) {
  if (e <= 0)
    return 0;
  if (e >= 255)
    return 255;
  return Math.round(e);
}
function Yj(e) {
  return `rgb(${tBt(e.r)}, ${tBt(e.g)}, ${tBt(e.b)})`;
}
function rBt(e) {
  const t = e.trim();
  if (t === "")
    return null;
  const s = Number(t.endsWith("%") ? Number(t.slice(0, -1)) / 100 : t);
  return Number.isFinite(s) ? s : null;
}
function YSe(e, t) {
  const s = e.split(/[,\s]+/u).map((n) => n.trim()).filter(Boolean);
  if (s.length !== t)
    return null;
  const o = [];
  for (const n of s) {
    const r = rBt(n);
    if (r === null)
      return null;
    o.push(r);
  }
  return o;
}
function wpi(e) {
  if (e.length !== 3)
    return null;
  return Yj({
    r: ME(e[0] ?? 0) * 255,
    g: ME(e[1] ?? 0) * 255,
    b: ME(e[2] ?? 0) * 255
  });
}
function Cpi(e) {
  if (e.length !== 3)
    return null;
  return Yj({ r: e[0] ?? 0, g: e[1] ?? 0, b: e[2] ?? 0 });
}
function xpi(e) {
  if (e.length !== 4)
    return null;
  const t = ME(e[0] ?? 0);
  const s = ME(e[1] ?? 0);
  const o = ME(e[2] ?? 0);
  const n = ME(e[3] ?? 0);
  return Yj({ r: 255 * (1 - t) * (1 - n), g: 255 * (1 - s) * (1 - n), b: 255 * (1 - o) * (1 - n) });
}
function bpi(e, t) {
  if (e.length !== 3)
    return null;
  const s = (e[0] ?? 0) * t % 360 / 60;
  const o = ME(e[1] ?? 0);
  const n = ME(e[2] ?? 0);
  const r = n * o;
  const i = r * (1 - Math.abs(s % 2 - 1));
  const a = n - r;
  let l = 0;
  let u = 0;
  let p = 0;
  if (s < 1) {
    l = r;
    u = i;
  } else if (s < 2) {
    l = i;
    u = r;
  } else if (s < 3) {
    u = r;
    p = i;
  } else if (s < 4) {
    u = i;
    p = r;
  } else if (s < 5) {
    l = i;
    p = r;
  } else {
    l = r;
    p = i;
  }
  return Yj({ r: (l + a) * 255, g: (u + a) * 255, b: (p + a) * 255 });
}
function kpi(e) {
  const t = rBt(e);
  if (t === null || t < 380 || t > 780)
    return null;
  let s = 0;
  let o = 0;
  let n = 0;
  if (t < 440) {
    s = -(t - 440) / 60;
    n = 1;
  } else if (t < 490) {
    o = (t - 440) / 50;
    n = 1;
  } else if (t < 510) {
    o = 1;
    n = -(t - 510) / 20;
  } else if (t < 580) {
    s = (t - 510) / 70;
    o = 1;
  } else if (t < 645) {
    s = 1;
    o = -(t - 645) / 65;
  } else {
    s = 1;
  }
  const r = t < 420 ? 0.3 + 0.7 * (t - 380) / 40 : t > 700 ? 0.3 + 0.7 * (780 - t) / 80 : 1;
  return Yj({ r: s * r * 255, g: o * r * 255, b: n * r * 255 });
}
function tve(e, t) {
  const s = e.trim();
  if (s === "")
    return null;
  if (t && s.includes("!")) {
    const r = vpi(s);
    if (r !== null)
      return r;
  }
  const o = Gmo[s] ?? Gmo[s.toLowerCase()];
  if (o !== undefined)
    return o;
  if (Bun.color(s, "css") !== null)
    return s;
  const n = s.toLowerCase();
  return n !== s && Bun.color(n, "css") !== null ? n : null;
}
function Rpi(e, t) {
  const s = e.trim();
  if (s === "" || s === "named")
    return tve(t, true);
  if (s === "HTML" || s === "Html" || s === "html") {
    const n = t.trim().replace(/^#/u, "");
    return /^[0-9A-Fa-f]{3,8}$/u.test(n) ? `#${n}` : null;
  }
  if (s === "wave")
    return kpi(t);
  const o = s.toLowerCase();
  if (s === "RGB")
    return Cpi(YSe(t, 3) ?? []);
  if (o === "rgb")
    return wpi(YSe(t, 3) ?? []);
  if (o === "cmyk")
    return xpi(YSe(t, 4) ?? []);
  if (o === "gray" || o === "grey") {
    const n = YSe(t, 1)?.[0];
    if (n === undefined)
      return null;
    const r = s === "Gray" || s === "Grey" ? n / 15 : n;
    const i = ME(r) * 255;
    return Yj({ r: i, g: i, b: i });
  }
  if (o === "hsb" || o === "hsv") {
    const n = YSe(t, 3);
    if (n === null)
      return null;
    return bpi(n, s === "Hsb" || s === "HSV" ? 1 : 360);
  }
  return tve(t, true);
}
function Spi(e, t) {
  const s = QSe(t).trim();
  if (s === "")
    return null;
  return e === null ? tve(s, true) : Rpi(e, s);
}
function vpi(e) {
  const t = e.split("!");
  if (t.length < 2)
    return null;
  const s = tve(t[0] ?? "", false);
  if (s === null)
    return null;
  let o = Bun.color(s, "{rgb}");
  if (o === null)
    return null;
  for (let n = 1;n < t.length; n += 2) {
    const r = rBt(t[n] ?? "");
    if (r === null)
      return null;
    const i = t[n + 1] ?? "white";
    const a = tve(i, false);
    if (a === null)
      return null;
    const l = Bun.color(a, "{rgb}");
    if (l === null)
      return null;
    const u = ME(r / 100);
    o = {
      r: o.r * u + l.r * (1 - u),
      g: o.g * u + l.g * (1 - u),
      b: o.b * u + l.b * (1 - u)
    };
  }
  return Yj(o);
}
function OYe(e, t) {
  const s = Spi(e, t);
  if (s === null)
    return null;
  const o = Bun.color(s, Tpi());
  if (o === null || !o.startsWith("\x1B[38;"))
    return null;
  return { foreground: o, background: o.replace("\x1B[38;", "\x1B[48;") };
}
function _Ye(e, t) {
  const s = OYe(e, t);
  if (s === null)
    return null;
  const { foreground: o } = s;
  return (n) => o + n.replaceAll(JSe, o) + JSe;
}
function $Se(e, t, s) {
  if (e.length === 0)
    return [];
  const o = Hmo(e, opi);
  if (o !== null)
    return o;
  return yw($o(t ? "^(" : "^", s), e, $o(t ? ")" : "", s));
}
function EYe(e, t, s) {
  if (e.length === 0)
    return [];
  const o = Hmo(e, npi);
  if (o !== null)
    return o;
  return yw($o(t ? "_(" : "_", s), e, $o(t ? ")" : "", s));
}

class iBt {
  #e;
  #t = 0;
  #s = null;
  #o = null;
  constructor(e) {
    this.#e = e;
  }
  render() {
    return ypi(this.parse(upi, false));
  }
  parse(e, t) {
    const s = [];
    while (this.#t < this.#e.length) {
      const o = this.#e[this.#t];
      if (o === "}") {
        if (t)
          break;
        this.#t++;
        continue;
      }
      eve(s, this.#r(e));
    }
    return s;
  }
  #n(e) {
    return Nmo(e, this.#s, this.#o);
  }
  #r(e) {
    const t = this.#e[this.#t];
    switch (t) {
      case "\\":
        return this.#i(e);
      case "{":
        return this.#a(e);
      case "^":
        this.#t++;
        return this.#y(e, true);
      case "_":
        this.#t++;
        return this.#y(e, false);
      case "$":
        this.#t++;
        return [];
      case "~":
        this.#t++;
        return $o(" ", this.#n(e));
      case "&":
        this.#t++;
        return $o("  ", this.#n(e));
      case "'": {
        let s = 0;
        while (this.#e[this.#t] === "'") {
          s++;
          this.#t++;
        }
        return $o(s <= 4 ? Pmo[s] : Pmo[1].repeat(s), this.#n(e));
      }
      case "%": {
        const s = this.#e.indexOf(`
`, this.#t);
        this.#t = s === -1 ? this.#e.length : s + 1;
        return [];
      }
      default:
        this.#t++;
        return $o(eBt(t, e), this.#n(e));
    }
  }
  #i(e) {
    this.#t++;
    if (this.#t >= this.#e.length)
      return [];
    const t = this.#e[this.#t];
    if (!/[A-Za-z]/.test(t)) {
      this.#t++;
      switch (t) {
        case "\\":
          return $o(`
`, this.#n(e));
        case "{":
        case "}":
        case "$":
        case "%":
        case "&":
        case "#":
        case "_":
        case " ":
        case ".":
          return $o(t, this.#n(e));
        case ",":
        case ":":
        case ";":
        case ">":
          return $o(" ", this.#n(e));
        case "!":
          return [];
        case "/":
          return [];
        case "|":
          return $o("\u2016", this.#n(e));
        case "(":
        case ")":
        case "[":
        case "]":
          return [];
        default:
          return $o(t, this.#n(e));
      }
    }
    let s = "";
    while (this.#t < this.#e.length && /[A-Za-z]/.test(this.#e[this.#t])) {
      s += this.#e[this.#t];
      this.#t++;
    }
    if (this.#e[this.#t] === "*")
      this.#t++;
    return this.#l(s, e);
  }
  #l(e, t) {
    const s = this.#n(t);
    const o = Dmo[e];
    if (o)
      return this.#g({ ...t, font: o }).text;
    const n = Umo[e];
    if (n !== undefined) {
      const l = this.#g({ ...t, ...n }).text;
      const u = n.bold === true ? "bold" : n.italic === true ? "italic" : null;
      return u === null ? l : hpi(l, u, t[u]);
    }
    if (ppi[e])
      return $o(QSe(this.#m()), s);
    if (e === "operatorname") {
      const l = QSe(this.#m());
      return $o(l + this.#_(), s);
    }
    const r = api[e];
    if (r)
      return Vj(this.#g(t).text, r);
    if (e === "frac" || e === "dfrac" || e === "tfrac" || e === "cfrac") {
      const l = this.#g(t);
      const u = this.#g(t);
      return this.#T(l, u, s);
    }
    if (e === "genfrac") {
      const l = this.#g(t).text;
      const u = this.#g(t).text;
      this.#m();
      this.#m();
      const p = this.#g(t);
      const c = this.#g(t);
      return yw(l, this.#T(p, c, s), u);
    }
    if (e === "binom" || e === "dbinom" || e === "tbinom") {
      const l = this.#g(t);
      const u = this.#g(t);
      return yw($o("C(", s), l.text, $o(", ", s), u.text, $o(")", s));
    }
    if (e === "sqrt")
      return this.#k(t);
    if (e === "not") {
      const l = this.#g(t);
      const u = ipi[vYe(l.text)];
      return u === undefined ? Vj(l.text, "\u0338") : $o(u, l.text[0]?.style ?? s);
    }
    if (e === "overset" || e === "stackrel")
      return this.#w(t);
    if (e === "underset")
      return this.#C(t);
    if (e === "prescript")
      return this.#b(t);
    const i = Opi[e];
    if (i !== undefined)
      return this.#S(t, i);
    if (e === "boxed" || e === "fbox")
      return uR(this.#g(t).text, "[", "]", s);
    if (e === "overbrace")
      return uR(this.#g(t).text, "\u23DE(", ")", s);
    if (e === "underbrace")
      return uR(this.#g(t).text, "\u23DF(", ")", s);
    if (e === "overbracket")
      return uR(this.#g(t).text, "\u23B4(", ")", s);
    if (e === "underbracket")
      return uR(this.#g(t).text, "\u23B5(", ")", s);
    if (e === "overparen")
      return uR(this.#g(t).text, "\u23DC(", ")", s);
    if (e === "underparen")
      return uR(this.#g(t).text, "\u23DD(", ")", s);
    if (e === "cancel")
      return Vj(this.#g(t).text, "\u0338");
    if (e === "bcancel")
      return Vj(this.#g(t).text, "\u20E5");
    if (e === "xcancel")
      return Vj(Vj(this.#g(t).text, "\u0338"), "\u20E5");
    if (e === "sout")
      return Vj(this.#g(t).text, "\u0336");
    if (e === "substack") {
      const l = this.#g(t).text;
      return l.map((u) => ({ ...u, text: u.text.replace(MYe, ",") }));
    }
    if (e === "left" || e === "right" || e === "middle")
      return this.#x(t);
    if (Epi.test(e))
      return this.#x(t);
    if (e === "begin")
      return this.#E(t);
    if (e === "end") {
      this.#m();
      return [];
    }
    if (e === "bmod")
      return $o(" mod ", s);
    if (e === "pmod")
      return uR(this.#g(t).text, "(mod ", ")", s);
    if (e === "pod")
      return uR(this.#g(t).text, "(", ")", s);
    if (e === "tag")
      return uR(this.#g(t).text, "(", ")", s);
    if (e === "label") {
      this.#m();
      return [];
    }
    if (e === "ref" || e === "eqref")
      return $o(`(${QSe(this.#m())})`, s);
    if (e === "url")
      return $o(QSe(this.#m()), s);
    if (e === "href") {
      this.#m();
      return this.#g(t).text;
    }
    if (e === "textcolor")
      return this.#c(this.#u(), t);
    if (e === "colorbox")
      return this.#f(this.#u(), t);
    if (e === "fcolorbox")
      return this.#d(t);
    if (e === "color")
      return this.#p();
    if (e === "normalcolor") {
      this.#s = null;
      return [];
    }
    if (e === "phantom" || e === "hphantom") {
      const l = this.#g(t).text;
      return $o(" ".repeat(J2t(l)), s);
    }
    if (e === "vphantom") {
      this.#g(t);
      return [];
    }
    if (lpi[e])
      return $o(e + this.#_(), s);
    const a = Fmo[e];
    if (a !== undefined)
      return $o(a, s);
    switch (e) {
      case "displaystyle":
      case "textstyle":
      case "scriptstyle":
      case "scriptscriptstyle":
      case "limits":
      case "nolimits":
      case "nonumber":
      case "notag":
      case "quad":
        return $o(e === "quad" ? "  " : "", s);
      case "qquad":
        return $o("    ", s);
      case "thinspace":
      case "enspace":
      case "medspace":
      case "thickspace":
      case "space":
        return $o(" ", s);
      case "negthinspace":
      case "negmedspace":
      case "negthickspace":
        return [];
    }
    return $o(e, s);
  }
  #a(e) {
    this.#t++;
    const t = this.#s;
    const s = this.#o;
    const o = this.parse(e, true);
    if (this.#e[this.#t] === "}")
      this.#t++;
    this.#s = t;
    this.#o = s;
    return o;
  }
  #u() {
    const e = this.#v();
    return OYe(e, this.#m());
  }
  #p() {
    const e = this.#u();
    if (e !== null)
      this.#s = e.foreground;
    return [];
  }
  #c(e, t) {
    const s = this.#s;
    if (e === null)
      return this.#g(t).text;
    this.#s = e.foreground;
    const o = this.#g(t).text;
    this.#s = s;
    return o;
  }
  #f(e, t) {
    const s = this.#o;
    if (e === null)
      return this.#g(t).text;
    this.#o = e.background;
    const o = this.#g(t).text;
    this.#o = s;
    return o;
  }
  #d(e) {
    const t = this.#v();
    const s = OYe(t, this.#m());
    const o = this.#v() ?? t;
    const n = OYe(o, this.#m());
    const r = this.#f(n, e);
    const i = Nmo(e, s?.foreground ?? this.#s, this.#o);
    return yw($o("[", i), r, $o("]", i));
  }
  #g(e) {
    while (this.#e[this.#t] === " ")
      this.#t++;
    const t = this.#e[this.#t];
    if (t === undefined)
      return { text: [], group: false };
    if (t === "{") {
      this.#t++;
      const s = this.parse(e, true);
      if (this.#e[this.#t] === "}")
        this.#t++;
      return { text: s, group: true };
    }
    if (t === "\\")
      return { text: this.#i(e), group: false };
    if (t === "^" || t === "_") {
      this.#t++;
      return { text: this.#y(e, t === "^"), group: false };
    }
    this.#t++;
    return { text: $o(eBt(t, e), this.#n(e)), group: false };
  }
  #m() {
    while (this.#e[this.#t] === " ")
      this.#t++;
    if (this.#e[this.#t] !== "{") {
      const s = this.#e[this.#t];
      if (s === undefined)
        return "";
      if (s === "\\") {
        let o = "\\";
        this.#t++;
        if (/[A-Za-z]/.test(this.#e[this.#t] ?? "")) {
          while (/[A-Za-z]/.test(this.#e[this.#t] ?? "")) {
            o += this.#e[this.#t];
            this.#t++;
          }
        } else {
          o += this.#e[this.#t] ?? "";
          this.#t++;
        }
        return o;
      }
      this.#t++;
      return s;
    }
    this.#t++;
    let e = 1;
    let t = "";
    while (this.#t < this.#e.length && e > 0) {
      const s = this.#e[this.#t];
      if (s === "\\") {
        t += s + (this.#e[this.#t + 1] ?? "");
        this.#t += 2;
        continue;
      }
      if (s === "{")
        e++;
      else if (s === "}") {
        e--;
        if (e === 0) {
          this.#t++;
          break;
        }
      }
      t += s;
      this.#t++;
    }
    return t;
  }
  #y(e, t) {
    const s = this.#n(e);
    const o = this.#g(e);
    return t ? $Se(o.text, o.group, s) : EYe(o.text, o.group, s);
  }
  #h(e, t) {
    if (!e.group || J2t(e.text) <= 1)
      return e.text;
    return uR(e.text, "(", ")", t);
  }
  #T(e, t, s) {
    const o = vYe(e.text);
    const n = vYe(t.text);
    const r = e.text[0]?.style ?? s;
    const i = [...e.text, ...t.text].every((l) => Kmo(l.style, r));
    const a = rpi[`${o}/${n}`];
    if (a && i)
      return $o(a, r);
    return yw(this.#h(e, s), $o("/", s), this.#h(t, s));
  }
  #w(e) {
    const t = this.#n(e);
    const s = this.#g(e);
    const o = this.#g(e);
    return yw(o.text, $Se(s.text, true, t));
  }
  #C(e) {
    const t = this.#n(e);
    const s = this.#g(e);
    const o = this.#g(e);
    return yw(o.text, EYe(s.text, true, t));
  }
  #b(e) {
    const t = this.#n(e);
    const s = this.#g(e);
    const o = this.#g(e);
    const n = this.#g(e);
    return yw($Se(s.text, true, t), EYe(o.text, true, t), n.text);
  }
  #S(e, t) {
    const s = this.#n(e);
    const o = this.#R(e);
    const n = this.#g(e);
    return yw($o(t, s), $Se(n.text, true, s), o === null ? [] : EYe(o.text, true, s));
  }
  #x(e) {
    while (this.#e[this.#t] === " ")
      this.#t++;
    const t = this.#e[this.#t];
    const s = this.#n(e);
    if (t === undefined)
      return [];
    if (t === ".") {
      this.#t++;
      return [];
    }
    if (t !== "\\") {
      this.#t++;
      return $o(eBt(t, e), s);
    }
    this.#t++;
    if (this.#t >= this.#e.length)
      return [];
    const o = this.#e[this.#t];
    if (!/[A-Za-z]/.test(o)) {
      this.#t++;
      switch (o) {
        case ".":
          return [];
        case "{":
          return $o("{", s);
        case "}":
          return $o("}", s);
        case "|":
          return $o("\u2016", s);
        default:
          return $o(o, s);
      }
    }
    let n = "";
    while (this.#t < this.#e.length && /[A-Za-z]/.test(this.#e[this.#t])) {
      n += this.#e[this.#t];
      this.#t++;
    }
    return $o(Fmo[n] ?? n, s);
  }
  #R(e) {
    const t = this.#v();
    if (t === null)
      return null;
    return { text: new iBt(t).parse(e, false), group: true };
  }
  #v() {
    while (this.#e[this.#t] === " ")
      this.#t++;
    if (this.#e[this.#t] !== "[")
      return null;
    this.#t++;
    let e = 1;
    let t = 0;
    let s = "";
    while (this.#t < this.#e.length && e > 0) {
      const o = this.#e[this.#t];
      if (o === "\\") {
        s += o + (this.#e[this.#t + 1] ?? "");
        this.#t += 2;
        continue;
      }
      if (o === "{")
        t++;
      else if (o === "}" && t > 0)
        t--;
      else if (t === 0 && o === "[")
        e++;
      else if (t === 0 && o === "]") {
        e--;
        if (e === 0) {
          this.#t++;
          break;
        }
      }
      s += o;
      this.#t++;
    }
    return s;
  }
  #k(e) {
    while (this.#e[this.#t] === " ")
      this.#t++;
    const t = this.#n(e);
    let s = $o("\u221A", t);
    const o = this.#R(e);
    if (o !== null) {
      const r = vYe(o.text);
      s = r === "2" ? $o("\u221A", t) : r === "3" ? $o("\u221B", t) : r === "4" ? $o("\u221C", t) : yw($Se(o.text, true, t), $o("\u221A", t));
    }
    const n = this.#g(e).text;
    return yw(s, J2t(n) > 1 ? uR(n, "(", ")", t) : n);
  }
  #E(e) {
    const t = this.#m().trim();
    if (t === "array" || t === "tabular" || t === "array*" || t === "tabular*") {
      this.#v();
      if (this.#e[this.#t] === "{")
        this.#m();
    } else if (t === "alignedat" || t === "alignedat*" || t === "alignat" || t === "alignat*" || t === "gatheredat") {
      this.#v();
      if (this.#e[this.#t] === "{")
        this.#m();
    }
    const s = [];
    while (this.#t < this.#e.length) {
      if (this.#e.startsWith("\\end", this.#t)) {
        this.#t += 4;
        this.#m();
        break;
      }
      eve(s, this.#r(e));
    }
    let o = mpi(s);
    if (t === "cases" || t === "cases*" || t === "dcases" || t === "dcases*" || t === "rcases" || t === "drcases") {
      o = o.map((i) => ({
        ...i,
        text: i.text.replace(/[ \t]*\n+[ \t]*/g, "; ").replace(/ {3,}/g, "  ")
      }));
    }
    const n = fpi[t];
    if (!n)
      return o;
    const r = this.#n(e);
    return yw($o(n[0], r), o, $o(n[1], r));
  }
  #_() {
    const e = this.#e[this.#t];
    if (e === undefined)
      return "";
    return /[A-Za-z0-9\\]/.test(e) ? " " : "";
  }
}
function Tw(e) {
  if (typeof e !== "string" || e.length === 0)
    return e;
  return new iBt(e).render();
}
function sve(e) {
  return _pi.has(e.endsWith("*") ? e.slice(0, -1) : e);
}
function Mpi(e) {
  let t = "";
  let s = 0;
  for (;; ) {
    const o = e.indexOf("\\begin{", s);
    if (o === -1)
      return t + ZSe(e.slice(s));
    const n = o + "\\begin{".length;
    const r = e.indexOf("}", n);
    if (r === -1)
      return t + ZSe(e.slice(s));
    const i = e.slice(n, r);
    const a = `\\end{${i}}`;
    const l = e.indexOf(a, r + 1);
    if (l === -1) {
      t += ZSe(e.slice(s, r + 1));
      s = r + 1;
      continue;
    }
    const u = l + a.length;
    if (!sve(i)) {
      t += ZSe(e.slice(s, o)) + e.slice(o, u);
      s = u;
      continue;
    }
    const p = e.lastIndexOf(`
`, o - 1) + 1;
    const c = e.slice(p, o);
    let d = c.includes("\\") || c.includes("=") ? p : o;
    if (d === o && c.trim() === "" && p > 0) {
      const f = p - 1;
      const g = e.lastIndexOf(`
`, f - 1) + 1;
      const m = e.slice(g, f);
      if (/[=([{]\s*$/.test(m))
        d = g;
    }
    t += ZSe(e.slice(s, d));
    t += Tw(e.slice(d, u)).replace(MYe, " ");
    s = u;
  }
}
function ZSe(e) {
  let t = "";
  let s = 0;
  for (let o = 0;o <= e.length; o++) {
    if (o !== e.length && e[o] !== `
`)
      continue;
    const n = e.slice(s, o);
    t += Api(n) ? Tw(n).replace(MYe, " ") : n;
    if (o !== e.length)
      t += `
`;
    s = o + 1;
  }
  return t;
}
function Api(e) {
  const t = e.trim();
  if (t === "" || !t.includes("\\"))
    return false;
  const s = /\\(?:begin|end)\{([^}]*)\}/.exec(t);
  if (s && !sve(s[1]))
    return false;
  if (!jmo.test(t))
    return false;
  return t.startsWith("\\") || /[=<>^_{}&]/.test(t);
}
function Ipi(e) {
  if (typeof e !== "string" || e.length === 0)
    return e;
  if (!e.includes("$") && !e.includes("\\(") && !e.includes("\\[") && !e.includes("\\begin") && !jmo.test(e)) {
    return e;
  }
  const t = (r) => Tw(r).replace(MYe, " ");
  let s = "";
  let o = 0;
  const n = e.length;
  while (o < n) {
    const r = e[o];
    if (r === "\\") {
      const i = e[o + 1];
      if (i === "\\") {
        s += "\\\\";
        o += 2;
        continue;
      }
      if (i === "$") {
        s += "$";
        o += 2;
        continue;
      }
      const a = KJ(e, o, o);
      if (a) {
        s += t(a.body);
        o = a.end;
        continue;
      }
      s += r;
      o++;
      continue;
    }
    if (r === "$") {
      const i = KJ(e, o, o);
      if (i) {
        s += t(i.body);
        o = i.end;
        continue;
      }
      if (e[o + 1] === "$") {
        s += "$$";
        o += 2;
        continue;
      }
      s += "$";
      o++;
      continue;
    }
    s += r;
    o++;
  }
  return Mpi(s);
}
var opi, npi, Pmo, rpi, ipi, api, lpi, Dmo, upi, Umo, nBt, ppi, cpi, dpi, fpi, Fmo, JSe = "\x1B[39m", Q2t = "\x1B[49m", sBt = "\x1B[1m", zmo = "\x1B[22m", oBt = "\x1B[3m", Bmo = "\x1B[23m", qmo, Gmo, Epi, Opi, MYe, jmo, _pi;
var AYe = k(() => {
  u2e();
  vA();
  opi = {
    "0": "\u2070",
    "1": "\xB9",
    "2": "\xB2",
    "3": "\xB3",
    "4": "\u2074",
    "5": "\u2075",
    "6": "\u2076",
    "7": "\u2077",
    "8": "\u2078",
    "9": "\u2079",
    "+": "\u207A",
    "-": "\u207B",
    "\u2212": "\u207B",
    "=": "\u207C",
    "(": "\u207D",
    ")": "\u207E",
    ".": "\xB7",
    " ": " ",
    a: "\u1D43",
    b: "\u1D47",
    c: "\u1D9C",
    d: "\u1D48",
    e: "\u1D49",
    f: "\u1DA0",
    g: "\u1D4D",
    h: "\u02B0",
    i: "\u2071",
    j: "\u02B2",
    k: "\u1D4F",
    l: "\u02E1",
    m: "\u1D50",
    n: "\u207F",
    o: "\u1D52",
    p: "\u1D56",
    r: "\u02B3",
    s: "\u02E2",
    t: "\u1D57",
    u: "\u1D58",
    v: "\u1D5B",
    w: "\u02B7",
    x: "\u02E3",
    y: "\u02B8",
    z: "\u1DBB",
    A: "\u1D2C",
    B: "\u1D2E",
    D: "\u1D30",
    E: "\u1D31",
    G: "\u1D33",
    H: "\u1D34",
    I: "\u1D35",
    J: "\u1D36",
    K: "\u1D37",
    L: "\u1D38",
    M: "\u1D39",
    N: "\u1D3A",
    O: "\u1D3C",
    P: "\u1D3E",
    R: "\u1D3F",
    T: "\u1D40",
    U: "\u1D41",
    V: "\u2C7D",
    W: "\u1D42",
    \u{3b1}: "\u1D45",
    \u{3b2}: "\u1D5D",
    \u{3b3}: "\u1D5E",
    \u{3b4}: "\u1D5F",
    \u{3b5}: "\u1D4B",
    \u{3b8}: "\u1DBF",
    \u{3b9}: "\u1DA5",
    \u{3c6}: "\u1D60",
    \u{3c7}: "\u1D61"
  };
  npi = {
    "0": "\u2080",
    "1": "\u2081",
    "2": "\u2082",
    "3": "\u2083",
    "4": "\u2084",
    "5": "\u2085",
    "6": "\u2086",
    "7": "\u2087",
    "8": "\u2088",
    "9": "\u2089",
    "+": "\u208A",
    "-": "\u208B",
    "\u2212": "\u208B",
    "=": "\u208C",
    "(": "\u208D",
    ")": "\u208E",
    " ": " ",
    a: "\u2090",
    e: "\u2091",
    h: "\u2095",
    i: "\u1D62",
    j: "\u2C7C",
    k: "\u2096",
    l: "\u2097",
    m: "\u2098",
    n: "\u2099",
    o: "\u2092",
    p: "\u209A",
    r: "\u1D63",
    s: "\u209B",
    t: "\u209C",
    u: "\u1D64",
    v: "\u1D65",
    x: "\u2093",
    \u{3b2}: "\u1D66",
    \u{3b3}: "\u1D67",
    \u{3c1}: "\u1D68",
    \u{3c6}: "\u1D69",
    \u{3c7}: "\u1D6A"
  };
  Pmo = ["", "\u2032", "\u2033", "\u2034", "\u2057"];
  rpi = {
    "1/2": "\xBD",
    "1/3": "\u2153",
    "2/3": "\u2154",
    "1/4": "\xBC",
    "3/4": "\xBE",
    "1/5": "\u2155",
    "2/5": "\u2156",
    "3/5": "\u2157",
    "4/5": "\u2158",
    "1/6": "\u2159",
    "5/6": "\u215A",
    "1/7": "\u2150",
    "1/8": "\u215B",
    "3/8": "\u215C",
    "5/8": "\u215D",
    "7/8": "\u215E",
    "1/9": "\u2151",
    "1/10": "\u2152",
    "0/3": "\u2189"
  };
  ipi = {
    "=": "\u2260",
    "<": "\u226E",
    ">": "\u226F",
    "\u2208": "\u2209",
    "\u220B": "\u220C",
    "\u2282": "\u2284",
    "\u2283": "\u2285",
    "\u2286": "\u2288",
    "\u2287": "\u2289",
    "\u2261": "\u2262",
    "\u2203": "\u2204",
    "\u2264": "\u2270",
    "\u2265": "\u2271",
    "\u2248": "\u2249",
    "\u2245": "\u2247",
    "\u223C": "\u2241",
    "\u2243": "\u2244",
    "\u2223": "\u2224",
    "\u2225": "\u2226",
    "\u227A": "\u2280",
    "\u227B": "\u2281",
    "\u2291": "\u22E2",
    "\u2292": "\u22E3"
  };
  api = {
    hat: "\u0302",
    widehat: "\u0302",
    check: "\u030C",
    widecheck: "\u030C",
    tilde: "\u0303",
    widetilde: "\u0303",
    acute: "\u0301",
    grave: "\u0300",
    dot: "\u0307",
    ddot: "\u0308",
    dddot: "\u20DB",
    ddddot: "\u20DC",
    breve: "\u0306",
    bar: "\u0304",
    vec: "\u20D7",
    overrightarrow: "\u20D7",
    overleftarrow: "\u20D6",
    mathring: "\u030A",
    overline: "\u0305",
    underline: "\u0332",
    underbar: "\u0332"
  };
  lpi = {
    sin: true,
    cos: true,
    tan: true,
    cot: true,
    sec: true,
    csc: true,
    sinh: true,
    cosh: true,
    tanh: true,
    coth: true,
    arcsin: true,
    arccos: true,
    arctan: true,
    arccot: true,
    arcsec: true,
    arccsc: true,
    sech: true,
    csch: true,
    ln: true,
    log: true,
    lg: true,
    exp: true,
    lim: true,
    limsup: true,
    liminf: true,
    max: true,
    min: true,
    sup: true,
    inf: true,
    det: true,
    dim: true,
    ker: true,
    hom: true,
    arg: true,
    deg: true,
    gcd: true,
    lcm: true,
    Pr: true,
    argmax: true,
    argmin: true,
    sgn: true,
    tr: true,
    rank: true,
    diag: true,
    var: true,
    cov: true,
    median: true,
    mod: true
  };
  Dmo = {
    mathbf: "bold",
    boldsymbol: "bolditalic",
    bm: "bolditalic",
    pmb: "bold",
    mathbb: "doublestruck",
    Bbb: "doublestruck",
    mathds: "doublestruck",
    mathbbm: "doublestruck",
    mathcal: "script",
    mathscr: "boldscript",
    mathfrak: "fraktur",
    mathbfscr: "boldscript",
    mathbfcal: "boldscript",
    mathbffrak: "boldfraktur",
    mathfrakbold: "boldfraktur",
    mathsf: "sans",
    mathsfit: "sansitalic",
    mathsfbf: "sansbold",
    mathbfsf: "sansbold",
    mathsfbfit: "sansbolditalic",
    mathbfsfit: "sansbolditalic",
    mathtt: "mono",
    mathit: "italic",
    mathbfit: "bolditalic"
  };
  upi = { font: null, bold: false, italic: false };
  Umo = {
    textbf: { bold: true },
    textit: { italic: true },
    textsl: { italic: true },
    emph: { italic: true },
    textmd: { bold: false },
    textup: { italic: false },
    texttt: {},
    textsf: {}
  };
  nBt = new Set([
    ...Object.keys(Dmo),
    ...Object.keys(Umo)
  ]);
  ppi = {
    text: true,
    textrm: true,
    textnormal: true,
    textsc: true,
    mathrm: true,
    mathnormal: true,
    mbox: true,
    hbox: true
  };
  cpi = {
    bold: { upper: 119808, lower: 119834, digit: 120782 },
    italic: { upper: 119860, lower: 119886 },
    bolditalic: { upper: 119912, lower: 119938 },
    script: { upper: 119964, lower: 119990 },
    boldscript: { upper: 120016, lower: 120042 },
    fraktur: { upper: 120068, lower: 120094 },
    doublestruck: { upper: 120120, lower: 120146, digit: 120792 },
    boldfraktur: { upper: 120172, lower: 120198 },
    sans: { upper: 120224, lower: 120250, digit: 120802 },
    sansbold: { upper: 120276, lower: 120302, digit: 120812 },
    sansitalic: { upper: 120328, lower: 120354 },
    sansbolditalic: { upper: 120380, lower: 120406 },
    mono: { upper: 120432, lower: 120458, digit: 120822 }
  };
  dpi = {
    "italic:h": "\u210E",
    "script:B": "\u212C",
    "script:E": "\u2130",
    "script:F": "\u2131",
    "script:H": "\u210B",
    "script:I": "\u2110",
    "script:L": "\u2112",
    "script:M": "\u2133",
    "script:R": "\u211B",
    "script:e": "\u212F",
    "script:g": "\u210A",
    "script:o": "\u2134",
    "fraktur:C": "\u212D",
    "fraktur:H": "\u210C",
    "fraktur:I": "\u2111",
    "fraktur:R": "\u211C",
    "fraktur:Z": "\u2128",
    "doublestruck:C": "\u2102",
    "doublestruck:H": "\u210D",
    "doublestruck:N": "\u2115",
    "doublestruck:P": "\u2119",
    "doublestruck:Q": "\u211A",
    "doublestruck:R": "\u211D",
    "doublestruck:Z": "\u2124"
  };
  fpi = {
    matrix: ["", ""],
    smallmatrix: ["", ""],
    array: ["", ""],
    tabular: ["", ""],
    pmatrix: ["(", ")"],
    bmatrix: ["[", "]"],
    Bmatrix: ["{", "}"],
    vmatrix: ["|", "|"],
    Vmatrix: ["\u2016", "\u2016"],
    cases: ["{", ""],
    "cases*": ["{", ""],
    dcases: ["{", ""],
    "dcases*": ["{", ""],
    rcases: ["", "}"],
    drcases: ["", "}"],
    aligned: ["", ""],
    "aligned*": ["", ""],
    alignedat: ["", ""],
    "alignedat*": ["", ""],
    align: ["", ""],
    "align*": ["", ""],
    alignat: ["", ""],
    "alignat*": ["", ""],
    split: ["", ""],
    gathered: ["", ""],
    equation: ["", ""],
    "equation*": ["", ""]
  };
  Fmo = {
    alpha: "\u03B1",
    beta: "\u03B2",
    gamma: "\u03B3",
    delta: "\u03B4",
    epsilon: "\u03F5",
    varepsilon: "\u03B5",
    zeta: "\u03B6",
    eta: "\u03B7",
    theta: "\u03B8",
    vartheta: "\u03D1",
    iota: "\u03B9",
    kappa: "\u03BA",
    varkappa: "\u03F0",
    lambda: "\u03BB",
    mu: "\u03BC",
    nu: "\u03BD",
    xi: "\u03BE",
    omicron: "\u03BF",
    pi: "\u03C0",
    varpi: "\u03D6",
    rho: "\u03C1",
    varrho: "\u03F1",
    sigma: "\u03C3",
    varsigma: "\u03C2",
    tau: "\u03C4",
    upsilon: "\u03C5",
    phi: "\u03D5",
    varphi: "\u03C6",
    chi: "\u03C7",
    psi: "\u03C8",
    omega: "\u03C9",
    digamma: "\u03DD",
    Gamma: "\u0393",
    Delta: "\u0394",
    Theta: "\u0398",
    Lambda: "\u039B",
    Xi: "\u039E",
    Pi: "\u03A0",
    Sigma: "\u03A3",
    Upsilon: "\u03A5",
    Phi: "\u03A6",
    Psi: "\u03A8",
    Omega: "\u03A9",
    sum: "\u2211",
    prod: "\u220F",
    coprod: "\u2210",
    int: "\u222B",
    iint: "\u222C",
    iiint: "\u222D",
    iiiint: "\u2A0C",
    oint: "\u222E",
    oiint: "\u222F",
    oiiint: "\u2230",
    bigcap: "\u22C2",
    bigcup: "\u22C3",
    bigsqcup: "\u2A06",
    bigvee: "\u22C1",
    bigwedge: "\u22C0",
    bigodot: "\u2A00",
    bigoplus: "\u2A01",
    bigotimes: "\u2A02",
    biguplus: "\u2A04",
    Cap: "\u22D2",
    Cup: "\u22D3",
    bigstar: "\u2605",
    pm: "\xB1",
    mp: "\u2213",
    times: "\xD7",
    div: "\xF7",
    ast: "\u2217",
    star: "\u22C6",
    circ: "\u2218",
    bullet: "\u2219",
    cdot: "\u22C5",
    cdotp: "\xB7",
    centerdot: "\xB7",
    cap: "\u2229",
    cup: "\u222A",
    uplus: "\u228E",
    sqcap: "\u2293",
    sqcup: "\u2294",
    vee: "\u2228",
    wedge: "\u2227",
    land: "\u2227",
    lor: "\u2228",
    setminus: "\u2216",
    smallsetminus: "\u2216",
    wr: "\u2240",
    amalg: "\u2A3F",
    diamond: "\u22C4",
    Diamond: "\u25C7",
    bigtriangleup: "\u25B3",
    bigtriangledown: "\u25BD",
    triangleleft: "\u25C1",
    triangleright: "\u25B7",
    lhd: "\u22B2",
    rhd: "\u22B3",
    unlhd: "\u22B4",
    unrhd: "\u22B5",
    oplus: "\u2295",
    ominus: "\u2296",
    otimes: "\u2297",
    oslash: "\u2298",
    odot: "\u2299",
    dagger: "\u2020",
    ddagger: "\u2021",
    boxplus: "\u229E",
    boxtimes: "\u22A0",
    boxdot: "\u22A1",
    boxminus: "\u229F",
    ltimes: "\u22C9",
    rtimes: "\u22CA",
    leftthreetimes: "\u22CB",
    rightthreetimes: "\u22CC",
    curlyvee: "\u22CE",
    curlywedge: "\u22CF",
    barwedge: "\u22BC",
    veebar: "\u22BB",
    doublebarwedge: "\u2A5E",
    circledast: "\u229B",
    circledcirc: "\u229A",
    circleddash: "\u229D",
    divideontimes: "\u22C7",
    dotplus: "\u2214",
    leq: "\u2264",
    le: "\u2264",
    geq: "\u2265",
    ge: "\u2265",
    ll: "\u226A",
    gg: "\u226B",
    neq: "\u2260",
    ne: "\u2260",
    equiv: "\u2261",
    doteq: "\u2250",
    sim: "\u223C",
    simeq: "\u2243",
    approx: "\u2248",
    approxeq: "\u224A",
    cong: "\u2245",
    propto: "\u221D",
    asymp: "\u224D",
    prec: "\u227A",
    succ: "\u227B",
    preceq: "\u2AAF",
    succeq: "\u2AB0",
    subset: "\u2282",
    supset: "\u2283",
    subseteq: "\u2286",
    supseteq: "\u2287",
    subsetneq: "\u228A",
    supsetneq: "\u228B",
    sqsubset: "\u228F",
    sqsupset: "\u2290",
    sqsubseteq: "\u2291",
    sqsupseteq: "\u2292",
    in: "\u2208",
    ni: "\u220B",
    owns: "\u220B",
    notin: "\u2209",
    mid: "\u2223",
    nmid: "\u2224",
    parallel: "\u2225",
    nparallel: "\u2226",
    perp: "\u22A5",
    vdash: "\u22A2",
    dashv: "\u22A3",
    models: "\u22A8",
    vDash: "\u22A8",
    Vdash: "\u22A9",
    bowtie: "\u22C8",
    smile: "\u2323",
    frown: "\u2322",
    between: "\u226C",
    lessgtr: "\u2276",
    gtrless: "\u2277",
    leqslant: "\u2A7D",
    geqslant: "\u2A7E",
    lesssim: "\u2272",
    gtrsim: "\u2273",
    lessapprox: "\u2A85",
    gtrapprox: "\u2A86",
    leqq: "\u2266",
    geqq: "\u2267",
    lneq: "\u2A87",
    gneq: "\u2A88",
    lneqq: "\u2268",
    gneqq: "\u2269",
    nleq: "\u2270",
    ngeq: "\u2271",
    nless: "\u226E",
    ngtr: "\u226F",
    nsubseteq: "\u2288",
    nsupseteq: "\u2289",
    nsim: "\u2241",
    ncong: "\u2247",
    triangleq: "\u225C",
    coloneqq: "\u2254",
    eqqcolon: "\u2255",
    risingdotseq: "\u2253",
    fallingdotseq: "\u2252",
    circeq: "\u2257",
    eqcirc: "\u2256",
    precsim: "\u227E",
    succsim: "\u227F",
    precapprox: "\u2AB7",
    succapprox: "\u2AB8",
    curlyeqprec: "\u22DE",
    curlyeqsucc: "\u22DF",
    Subset: "\u22D0",
    Supset: "\u22D1",
    subseteqq: "\u2AC5",
    supseteqq: "\u2AC6",
    subsetneqq: "\u2ACB",
    supsetneqq: "\u2ACC",
    Vvdash: "\u22AA",
    shortmid: "\u2223",
    shortparallel: "\u2225",
    pitchfork: "\u22D4",
    leftarrow: "\u2190",
    gets: "\u2190",
    rightarrow: "\u2192",
    to: "\u2192",
    leftrightarrow: "\u2194",
    Leftarrow: "\u21D0",
    Rightarrow: "\u21D2",
    Leftrightarrow: "\u21D4",
    uparrow: "\u2191",
    downarrow: "\u2193",
    updownarrow: "\u2195",
    Uparrow: "\u21D1",
    Downarrow: "\u21D3",
    Updownarrow: "\u21D5",
    mapsto: "\u21A6",
    longmapsto: "\u27FC",
    hookleftarrow: "\u21A9",
    hookrightarrow: "\u21AA",
    leftharpoonup: "\u21BC",
    rightharpoonup: "\u21C0",
    leftharpoondown: "\u21BD",
    rightharpoondown: "\u21C1",
    rightleftharpoons: "\u21CC",
    longleftarrow: "\u27F5",
    longrightarrow: "\u27F6",
    longleftrightarrow: "\u27F7",
    Longleftarrow: "\u27F8",
    Longrightarrow: "\u27F9",
    Longleftrightarrow: "\u27FA",
    implies: "\u27F9",
    impliedby: "\u27F8",
    iff: "\u27FA",
    nearrow: "\u2197",
    searrow: "\u2198",
    swarrow: "\u2199",
    nwarrow: "\u2196",
    nleftarrow: "\u219A",
    nrightarrow: "\u219B",
    leadsto: "\u21DD",
    rightsquigarrow: "\u21DD",
    leftrightsquigarrow: "\u21AD",
    twoheadrightarrow: "\u21A0",
    twoheadleftarrow: "\u219E",
    leftrightharpoons: "\u21CB",
    rightleftarrows: "\u21C4",
    leftrightarrows: "\u21C6",
    leftleftarrows: "\u21C7",
    rightrightarrows: "\u21C9",
    upuparrows: "\u21C8",
    downdownarrows: "\u21CA",
    circlearrowleft: "\u21BA",
    circlearrowright: "\u21BB",
    curvearrowleft: "\u21B6",
    curvearrowright: "\u21B7",
    dashleftarrow: "\u21E0",
    dashrightarrow: "\u21E2",
    Lleftarrow: "\u21DA",
    Rrightarrow: "\u21DB",
    leftarrowtail: "\u21A2",
    rightarrowtail: "\u21A3",
    looparrowleft: "\u21AB",
    looparrowright: "\u21AC",
    multimap: "\u22B8",
    infty: "\u221E",
    partial: "\u2202",
    nabla: "\u2207",
    forall: "\u2200",
    exists: "\u2203",
    nexists: "\u2204",
    emptyset: "\u2205",
    varnothing: "\u2205",
    neg: "\xAC",
    lnot: "\xAC",
    top: "\u22A4",
    bot: "\u22A5",
    angle: "\u2220",
    measuredangle: "\u2221",
    sphericalangle: "\u2222",
    aleph: "\u2135",
    beth: "\u2136",
    gimel: "\u2137",
    daleth: "\u2138",
    hbar: "\u210F",
    hslash: "\u210F",
    ell: "\u2113",
    imath: "\u0131",
    jmath: "\u0237",
    wp: "\u2118",
    Re: "\u211C",
    Im: "\u2111",
    mho: "\u2127",
    complement: "\u2201",
    surd: "\u221A",
    flat: "\u266D",
    natural: "\u266E",
    sharp: "\u266F",
    clubsuit: "\u2663",
    diamondsuit: "\u2666",
    heartsuit: "\u2665",
    spadesuit: "\u2660",
    clubs: "\u2663",
    diamonds: "\u2666",
    hearts: "\u2665",
    spades: "\u2660",
    therefore: "\u2234",
    because: "\u2235",
    checkmark: "\u2713",
    maltese: "\u2720",
    dag: "\u2020",
    ddag: "\u2021",
    S: "\xA7",
    P: "\xB6",
    copyright: "\xA9",
    circledR: "\xAE",
    pounds: "\xA3",
    yen: "\xA5",
    euro: "\u20AC",
    degree: "\xB0",
    prime: "\u2032",
    backprime: "\u2035",
    colon: ":",
    semicolon: ";",
    neper: "\u20AA",
    square: "\u25A1",
    Box: "\u25A1",
    blacksquare: "\u25A0",
    lozenge: "\u25CA",
    blacklozenge: "\u29EB",
    triangle: "\u25B3",
    blacktriangle: "\u25B4",
    blacktriangledown: "\u25BE",
    blacktriangleleft: "\u25C2",
    blacktriangleright: "\u25B8",
    diagup: "\u2571",
    diagdown: "\u2572",
    backepsilon: "\u03F6",
    Game: "\u2141",
    eth: "\xF0",
    ldots: "\u2026",
    dots: "\u2026",
    cdots: "\u22EF",
    vdots: "\u22EE",
    ddots: "\u22F1",
    hdots: "\u2026",
    mathellipsis: "\u2026",
    dotsc: "\u2026",
    dotsb: "\u22EF",
    dotsm: "\u22EF",
    dotsi: "\u22EF",
    langle: "\u27E8",
    rangle: "\u27E9",
    lceil: "\u2308",
    rceil: "\u2309",
    lfloor: "\u230A",
    rfloor: "\u230B",
    lbrace: "{",
    rbrace: "}",
    lbrack: "[",
    rbrack: "]",
    vert: "|",
    Vert: "\u2016",
    lvert: "|",
    rvert: "|",
    lVert: "\u2016",
    rVert: "\u2016",
    backslash: "\\",
    slash: "/",
    ulcorner: "\u231C",
    urcorner: "\u231D",
    llcorner: "\u231E",
    lrcorner: "\u231F",
    lmoustache: "\u23B0",
    rmoustache: "\u23B1",
    lgroup: "\u27EE",
    rgroup: "\u27EF",
    bracevert: "\u23AA",
    Reals: "\u211D",
    Complex: "\u2102",
    Natural: "\u2115",
    Integer: "\u2124",
    Rational: "\u211A"
  };
  qmo = {
    bold: false,
    italic: false,
    foreground: null,
    background: null
  };
  Gmo = {
    black: "#000000",
    blue: "#0000ff",
    brown: "#a52a2a",
    cyan: "#00ffff",
    darkgray: "#404040",
    darkgrey: "#404040",
    gray: "#808080",
    green: "#00ff00",
    grey: "#808080",
    lightgray: "#c0c0c0",
    lightgrey: "#c0c0c0",
    lime: "#00ff00",
    magenta: "#ff00ff",
    olive: "#808000",
    orange: "#ffa500",
    pink: "#ffc0cb",
    purple: "#800080",
    red: "#ff0000",
    teal: "#008080",
    violet: "#ee82ee",
    white: "#ffffff",
    yellow: "#ffff00"
  };
  Epi = /^(?:[bB]igg?|[bB]igg?[lrm])$/;
  Opi = {
    xleftarrow: "\u2190",
    xrightarrow: "\u2192",
    xleftrightarrow: "\u2194",
    xLeftarrow: "\u21D0",
    xRightarrow: "\u21D2",
    xLeftrightarrow: "\u21D4",
    xhookleftarrow: "\u21A9",
    xhookrightarrow: "\u21AA",
    xtwoheadleftarrow: "\u219E",
    xtwoheadrightarrow: "\u21A0",
    xmapsto: "\u21A6",
    xrightharpoonup: "\u21C0",
    xrightharpoondown: "\u21C1",
    xleftharpoonup: "\u21BC",
    xleftharpoondown: "\u21BD",
    xrightleftharpoons: "\u21CC",
    xleftrightharpoons: "\u21CB"
  };
  MYe = /\n+/g;
  jmo = /\\(?:operatorname|frac|dfrac|tfrac|cfrac|genfrac|sqrt|sum|prod|coprod|int|iint|iiint|lim|alpha|beta|gamma|delta|epsilon|varepsilon|theta|lambda|mu|sigma|phi|varphi|pi|omega|infty|partial|nabla|forall|exists|mathbb|mathcal|mathscr|mathbf|mathrm|left|right|begin|phantom|hphantom|vphantom|cdots|ldots|dots|to|rightarrow|leftarrow|leq|geq|neq|times|cdot|overline|underline|vec|hat|bar|textbf|textit|textsl|emph|textmd|textup|texttt|textsf|textcolor|color|normalcolor|colorbox|fcolorbox)\b/;
  _pi = new Set([
    "matrix",
    "smallmatrix",
    "pmatrix",
    "bmatrix",
    "Bmatrix",
    "vmatrix",
    "Vmatrix",
    "cases",
    "dcases",
    "rcases",
    "drcases",
    "aligned",
    "alignedat",
    "align",
    "alignat",
    "split",
    "gathered",
    "gatheredat",
    "gather",
    "multline",
    "equation",
    "eqnarray",
    "array",
    "subarray"
  ]);
});


AYe();

export function renderMath(text) {
  return Ipi(text);
}
export function latexToUnicode(tex) {
  return Tw(tex);
}
