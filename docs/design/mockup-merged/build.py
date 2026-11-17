"""合并 docs/design/mockup (V1) 与 mockup-v2 (V2) 两版 UI 原型 -> mockup-merged。

策略：以 V2 为壳；V1 的四个视图（总览/行情/简报/设计规范）以「渲染后 DOM 快照 + Shadow DOM」
方式挂载，彻底隔离两套 CSS，避免类名冲突；V1 的图标 sprite 一并注入 shadow。
"""
from __future__ import annotations

import io
import os
import re

from pathlib import Path

ROOT = Path(r"D:\Code\4_个人研发\economic-analysis-tool")
V1 = ROOT / "docs" / "design" / "mockup" / "index.html"
V2 = ROOT / "docs" / "design" / "mockup-v2" / "index.html"
DOM = ROOT / "data" / "_v1_dom.html"
OUT = ROOT / "docs" / "design" / "mockup-merged" / "index.html"

V1_VIEW_IDS = ["overview", "market", "brief", "tokens"]


def shadow_css(css: str) -> str:
    """把 V1 全局 CSS 改造成 shadow 内样式：body -> .v1-page，丢弃 html/:root，主题规则改写。"""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"(?m)^\s*:root\s*\{[^}]*\}", "", css)
    css = re.sub(r"(?m)^\s*html\s*\{[^}]*\}", "", css)

    def sel_fix(sel: str) -> str:
        s = sel.strip()
        if not s:
            return ""
        m = re.match(r'^html\[data-theme=["\']?(light|dark)["\']?\](.*)$', s)
        if m:
            rest = m.group(2).strip()
            base = '.v1-page[data-theme="%s"]' % m.group(1)
            return (base + " " + rest) if rest else base
        if re.match(r"^body(\b|\.|\[|:|\s)", s):
            return re.sub(r"^body", ".v1-page", s, count=1)
        if re.match(r"^html(\b|\.|\[|:|\s)", s):
            return ""
        return s

    out = []
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        sel = css[i:j].strip()
        depth, k = 0, j
        while k < n:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        body = css[j + 1 : k]
        if sel.startswith("@media") or sel.startswith("@supports"):
            out.append(sel + "{" + shadow_css(body) + "}")
        else:
            sels = [sel_fix(s) for s in sel.split(",")]
            sels = [s for s in sels if s]
            if sels:
                out.append(", ".join(sels) + "{" + body + "}")
        i = k + 1
    extra = """
.v1-page { --info: #4CC2FF; --row-h: 36px; --primary: var(--accent); --ghost: var(--surface-2); }
.v1-page[data-theme="light"] { --info: #0B6FB3; --primary: var(--accent); --ghost: var(--surface-2); }
.v1-page { color: var(--text); font-family: var(--sans); font-size: 13px; line-height: 1.45;
  font-variant-numeric: tabular-nums; -webkit-font-smoothing: antialiased; }
"""
    return "\n".join(out) + extra


def main() -> None:
    v2 = io.open(V2, encoding="utf-8").read()
    v1 = io.open(V1, encoding="utf-8").read()
    dom = io.open(DOM, encoding="utf-8", errors="replace").read()
    dom = dom[dom.find("<!DOCTYPE html>") :]

    # 1) sprite
    m = re.search(r'(?s)<svg[^>]*aria-hidden="true"[^>]*>\s*<symbol.*?</svg>', v1)
    if not m:
        raise SystemExit("sprite not found in V1")
    sprite = m.group(0)

    # 2) V1 渲染后的四个视图（section 内部可能嵌套 <section>，按下一个 view 起点切分）
    templates = []
    view_starts = []
    for mm in re.finditer(r'<section class="view[^"]*" id="view-([\w-]+)"[^>]*>', dom):
        view_starts.append((mm.group(1), mm.start(), mm.end()))
    view_starts.sort(key=lambda x: x[1])
    for idx_v, (vid, start, tag_end) in enumerate(view_starts):
        end = view_starts[idx_v + 1][1] if idx_v + 1 < len(view_starts) else dom.find("</main>", start)
        if end < 0:
            raise SystemExit("cannot locate end of section %s" % vid)
        inner = dom[tag_end:end]
        inner = re.sub(r"</section>\s*$", "", inner.strip())
        templates.append('<template id="v1-tpl-%s">%s</template>' % (vid, inner))
    got = [t.split('"')[1] for t in templates]
    missing = [v for v in V1_VIEW_IDS if "v1-tpl-" + v not in got]
    if missing:
        raise SystemExit("missing rendered sections: %s (got %s)" % (missing, got))

    css = re.findall(r"(?s)<style>(.*?)</style>", v1)[0]
    css_scoped = shadow_css(css)

    blocks = """
<template id="v1-sprite">%s</template>
<script type="text/plain" id="v1-css">%s</script>
%s
""" % (sprite, css_scoped, "\n".join(templates))

    # 3) 空挂载点插入 main
    mounts = "\n".join(
        '<section class="view" id="view-%s" data-v1="%s"></section>' % (vid, vid) for vid in V1_VIEW_IDS
    )
    merged = v2.replace("<body>", "<body>\n" + blocks + "\n", 1)
    idx = merged.rfind("</main>")
    if idx < 0:
        raise SystemExit("</main> not found")
    merged = merged[:idx] + mounts + "\n" + merged[idx:]

    # 4) 导航替换
    nav_start = merged.find('<nav class="nav"')
    nav_end = merged.find("</nav>", nav_start) + len("</nav>")
    nav_new = """<nav class="nav">
    <div class="nav-group">
      <div class="nav-label">今日</div>
      <button class="nav-item active" data-view="overview" aria-current="page"><svg class="ic" viewBox="0 0 24 24"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/></svg><span class="nav-text">总览</span></button>
      <button class="nav-item" data-view="brief"><svg class="ic" viewBox="0 0 24 24"><path d="M6 3.5h9l4 4v13H6z"/><path d="M14.5 3.5v4.5H19M9 12h6M9 16h6"/></svg><span class="nav-text">简报</span></button>
    </div>
    <div class="nav-group">
      <div class="nav-label">市场</div>
      <button class="nav-item" data-view="market"><svg class="ic" viewBox="0 0 24 24"><path d="M3.5 17.5l5-5 3.5 3 8-8.5"/><path d="M14.5 7h5.5v5.5"/></svg><span class="nav-text">行情</span></button>
      <button class="nav-item soon" data-soon="利率"><svg class="ic" viewBox="0 0 24 24"><path d="M5 19L19 5"/><circle cx="7.5" cy="7.5" r="2"/><circle cx="16.5" cy="16.5" r="2"/></svg><span class="nav-text">利率</span><span class="nav-badge soon-badge">待接入</span></button>
      <button class="nav-item soon" data-soon="日历"><svg class="ic" viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/></svg><span class="nav-text">日历</span><span class="nav-badge soon-badge">待接入</span></button>
    </div>
    <div class="nav-group">
      <div class="nav-label">研判</div>
      <button class="nav-item" data-view="compass"><svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/></svg><span class="nav-text">周期罗盘</span></button>
      <button class="nav-item" data-view="history"><svg class="ic" viewBox="0 0 24 24"><path d="M3.5 15c3-5 5 3 8-1s5 1 9-4"/><path d="M3.5 19c3-5 5 3 8-1s5 1 9-4"/></svg><span class="nav-text">世界长河</span></button>
      <button class="nav-item" data-view="pipeline"><svg class="ic" viewBox="0 0 24 24"><circle cx="5.5" cy="6" r="2"/><circle cx="18.5" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M7.5 6h9M6.5 8l4.5 8M17.5 8l-4.5 8"/></svg><span class="nav-text">透明管线</span></button>
      <button class="nav-item" data-view="alerts"><svg class="ic" viewBox="0 0 24 24"><path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2.5h-15z"/><path d="M10 21h4"/></svg><span class="nav-text">预警台</span><span class="nav-badge hot">3</span></button>
    </div>
    <div class="nav-group">
      <div class="nav-label">系统</div>
      <button class="nav-item" data-view="tokens"><svg class="ic" viewBox="0 0 24 24"><path d="M12 3a9 9 0 100 18c1.4 0 2.2-.9 2.2-2 0-1.5-1.2-1.7-1.2-3 0-1.1.9-2 2-2h1c3.3 0 5-2 5-4.5C21 6 17 3 12 3z"/><circle cx="7.6" cy="10.4" r="1"/><circle cx="10.6" cy="7.2" r="1"/><circle cx="15.4" cy="7.8" r="1"/></svg><span class="nav-text">设计规范</span></button>
    </div>
  </nav>"""
    merged = merged[:nav_start] + nav_new + merged[nav_end:]

    # 5) VIEWS / 默认视图 / PALETTE
    views_old = """var VIEWS = {
    compass: { name: '周期罗盘', group: '研判', title: '周期罗盘 · 美国长债务周期晚期' },"""
    views_new = """var VIEWS = {
    overview: { name: '总览', group: '今日', title: '今日总览 · 关键变化与主线' },
    brief: { name: '简报', group: '今日', title: '每日简报 · 证据与判断' },
    market: { name: '行情', group: '市场', title: '市场行情 · 跨资产快照' },
    compass: { name: '周期罗盘', group: '研判', title: '周期罗盘 · 美国长债务周期晚期' },"""
    if views_old not in merged:
        raise SystemExit("VIEWS anchor missing")
    merged = merged.replace(views_old, views_new, 1)
    merged = merged.replace(
        "    alerts: { name: '预警台', group: '研判', title: '预警台 · 阈值与日历' }\n  };",
        "    alerts: { name: '预警台', group: '研判', title: '预警台 · 阈值与日历' },\n"
        "    tokens: { name: '设计规范', group: '系统', title: '设计规范 · Design Tokens' }\n  };",
        1,
    )
    for old, new in [
        ("var currentView = 'compass';", "var currentView = 'overview';"),
        ("if (!VIEWS[v]) v = prefs.view || 'compass';", "if (!VIEWS[v]) v = prefs.view || 'overview';"),
        ("if (!VIEWS[v]) v = 'compass';", "if (!VIEWS[v]) v = 'overview';"),
        ("if (!VIEWS[view]) view = 'compass';", "if (!VIEWS[view]) view = 'overview';"),
    ]:
        merged = merged.replace(old, new, 1)

    pal_old = "  var PALETTE = [\n"
    pal_new = """  var PALETTE = [
    { kind: 'view', view: 'overview', title: '总览', hint: '视图 · 默认', icon: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>' },
    { kind: 'view', view: 'brief', title: '每日简报', hint: '视图', icon: '<path d="M6 3.5h9l4 4v13H6z"/><path d="M14.5 3.5v4.5H19M9 12h6M9 16h6"/>' },
    { kind: 'view', view: 'market', title: '市场行情', hint: '视图', icon: '<path d="M3.5 17.5l5-5 3.5 3 8-8.5"/><path d="M14.5 7h5.5v5.5"/>' },
"""
    if pal_old not in merged:
        raise SystemExit("PALETTE anchor missing")
    merged = merged.replace(pal_old, pal_new, 1)

    # 6) shadow 挂载逻辑
    mount_js = """
  var V1_VIEWS = { overview: 1, brief: 1, market: 1, tokens: 1 };
  function mountV1(view) {
    if (!V1_VIEWS[view]) return;
    var host = document.getElementById('view-' + view);
    if (!host || host.__v1Mounted) return;
    var tpl = document.getElementById('v1-tpl-' + view);
    var sprite = document.getElementById('v1-sprite');
    var cssEl = document.getElementById('v1-css');
    if (!tpl || !sprite || !cssEl) return;
    host.__v1Mounted = true;
    var root = host.attachShadow({ mode: 'open' });
    var theme = document.documentElement.dataset.theme || 'dark';
    root.innerHTML = '<style>' + cssEl.textContent + '</style>' +
      '<div class="v1-page" data-theme="' + theme + '">' +
      sprite.innerHTML + tpl.innerHTML + '</div>';
    root.addEventListener('click', function (e) {
      var b = e.target && e.target.closest ? e.target.closest('[data-go]') : null;
      if (b && VIEWS[b.dataset.go]) setView(b.dataset.go, { push: true });
    });
  }
  new MutationObserver(function () {
    var theme = document.documentElement.dataset.theme || 'dark';
    $$('section[data-v1]').forEach(function (host) {
      if (!host.shadowRoot) return;
      var page = host.shadowRoot.querySelector('.v1-page');
      if (page) page.dataset.theme = theme;
    });
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

"""
    anchor = "  function setView(view, opts) {"
    if anchor not in merged:
        raise SystemExit("setView anchor missing")
    merged = merged.replace(anchor, mount_js + anchor, 1)
    merged = merged.replace("    if (view === 'history') buildTimeline();", "    if (view === 'history') buildTimeline();\n    mountV1(view);", 1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(merged)
    print("merged bytes:", os.path.getsize(OUT))
    print("shadow css bytes:", len(css_scoped))
    print("templates:", [t.split('"')[1] for t in templates])


if __name__ == "__main__":
    main()
