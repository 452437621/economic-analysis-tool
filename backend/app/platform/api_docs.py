"""本地自托管的接口文档页。

FastAPI 默认的 ``/docs`` 会从 ``cdn.jsdelivr.net`` 加载 swagger-ui 静态资源，在受限网络
（本项目的目标环境之一）下会直接白屏。这里改为零外部依赖的自渲染页面：浏览器直接读取
``/openapi.json``，按分组列出全部端点，支持搜索与展开查看参数、请求体与响应码。

只读页面，不发起任何业务请求；需要试调用时用页面给出的 curl 片段。
"""

from __future__ import annotations

from html import escape

_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title} · 接口文档</title>
<style>
  :root {{
    --bg: #0b0e11; --surface: #12161b; --surface-2: #171c22; --border: #242c35;
    --text: #e6edf3; --muted: #8b98a5; --dim: #5f6b77;
    --accent: #4da3ff; --up: #3fb950; --down: #f85149; --warn: #d29922;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text);
    font: 14px/1.55 "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; }}
  header {{ position: sticky; top: 0; z-index: 5; background: rgba(11,14,17,.94);
    border-bottom: 1px solid var(--border); padding: 14px 24px; backdrop-filter: blur(6px); }}
  .head-row {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }}
  h1 {{ font-size: 17px; margin: 0 0 2px; letter-spacing: .3px; }}
  .sub {{ color: var(--muted); font-size: 12px; }}
  .badge {{ border: 1px solid var(--border); border-radius: 999px; padding: 1px 9px;
    font-size: 11px; color: var(--muted); }}
  input[type="search"] {{ margin-top: 10px; width: 100%; max-width: 520px; padding: 7px 11px;
    border-radius: 8px; border: 1px solid var(--border); background: var(--surface-2);
    color: var(--text); font-size: 13px; outline: none; }}
  input[type="search"]:focus {{ border-color: var(--accent); }}
  main {{ padding: 18px 24px 64px; max-width: 1180px; }}
  h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: .12em; color: var(--muted);
    margin: 26px 0 8px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }}
  .op {{ border: 1px solid var(--border); border-radius: 9px; background: var(--surface);
    margin-bottom: 7px; overflow: hidden; }}
  .op > summary {{ display: flex; align-items: center; gap: 10px; padding: 8px 12px;
    cursor: pointer; list-style: none; }}
  .op > summary::-webkit-details-marker {{ display: none; }}
  .op > summary:hover {{ background: var(--surface-2); }}
  .m {{ font: 600 11px/1 ui-monospace, Consolas, monospace; padding: 4px 7px; border-radius: 5px;
    min-width: 52px; text-align: center; letter-spacing: .04em; }}
  .m-get {{ background: rgba(77,163,255,.14); color: var(--accent); }}
  .m-post {{ background: rgba(63,185,80,.14); color: var(--up); }}
  .m-patch, .m-put {{ background: rgba(210,153,34,.16); color: var(--warn); }}
  .m-delete {{ background: rgba(248,81,73,.14); color: var(--down); }}
  code.path {{ font: 13px/1.3 ui-monospace, Consolas, monospace; color: var(--text); }}
  .sum {{ color: var(--muted); font-size: 12px; margin-left: auto; text-align: right;
    max-width: 46%; }}
  .body {{ padding: 4px 14px 14px 14px; border-top: 1px solid var(--border); }}
  .body p {{ color: var(--muted); margin: 10px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 8px; }}
  th, td {{ text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--border);
    vertical-align: top; }}
  th {{ color: var(--dim); font-weight: 500; font-size: 11px; text-transform: uppercase;
    letter-spacing: .08em; }}
  td code, .mono {{ font-family: ui-monospace, Consolas, monospace; color: var(--accent); }}
  pre {{ background: var(--surface-2); border: 1px solid var(--border); border-radius: 7px;
    padding: 9px 11px; overflow-x: auto; font-size: 12px; margin: 8px 0 0; }}
  .empty {{ color: var(--dim); padding: 20px 0; }}
  footer {{ color: var(--dim); font-size: 12px; padding: 0 24px 40px; }}
  a {{ color: var(--accent); }}
</style>
</head>
<body>
<header>
  <div class="head-row">
    <h1>{title}</h1>
    <span class="badge">v{version}</span>
    <span class="badge" id="stat">加载中…</span>
    <span class="sub">本地自托管文档（不依赖外部 CDN）· 原始规范：<a href="/openapi.json">/openapi.json</a></span>
  </div>
  <input id="q" type="search" placeholder="搜索路径、方法或摘要，例如 lens / cycle / forecast" />
</header>
<main id="list"></main>
<footer>本页面只读取 OpenAPI 规范，不会调用业务接口。前端界面：<a href="/">返回 EPIC 主界面</a>。</footer>
<script>
(function () {{
  var list = document.getElementById("list");
  var stat = document.getElementById("stat");
  var q = document.getElementById("q");
  var state = {{ spec: null, query: "" }};

  function esc(text) {{
    return String(text == null ? "" : text).replace(/[&<>"]/g, function (c) {{
      return {{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }}[c];
    }});
  }}

  function groupOf(path, op) {{
    var tags = op.tags || [];
    if (tags.length) return tags[0];
    var parts = path.split("/").filter(Boolean);
    return parts.length > 1 ? parts[0] + "/" + parts[1] : (parts[0] || "root");
  }}

  function typeOf(schema) {{
    if (!schema) return "—";
    if (schema.$ref) return schema.$ref.split("/").pop();
    if (schema.type === "array") return typeOf(schema.items) + "[]";
    if (schema.anyOf) return schema.anyOf.map(typeOf).join(" | ");
    if (schema.oneOf) return schema.oneOf.map(typeOf).join(" | ");
    if (schema.enum) return "enum(" + schema.enum.join(", ") + ")";
    if (schema.type) return schema.type;
    if (schema.properties) return "object";
    return "—";
  }}

  function paramsTable(op) {{
    var params = op.parameters || [];
    var body = op.requestBody;
    var html = "";
    if (params.length) {{
      html += "<table><thead><tr><th>参数</th><th>位置</th><th>类型</th><th>必填</th><th>说明</th></tr></thead><tbody>";
      params.forEach(function (p) {{
        html += "<tr><td class='mono'>" + esc(p.name) + "</td><td>" + esc(p.in) + "</td><td>" + esc(typeOf(p.schema)) +
          "</td><td>" + (p.required ? "是" : "否") + "</td><td>" + esc(p.description || "") + "</td></tr>";
      }});
      html += "</tbody></table>";
    }}
    if (body && body.content) {{
      var keys = Object.keys(body.content);
      var media = keys[0];
      html += "<table><thead><tr><th>请求体</th><th>类型</th><th>必填</th></tr></thead><tbody>";
      html += "<tr><td class='mono'>" + esc(media) + "</td><td>" + esc(typeOf(body.content[media].schema)) +
        "</td><td>" + (body.required ? "是" : "否") + "</td></tr></tbody></table>";
    }}
    var responses = op.responses || {{}};
    var codes = Object.keys(responses);
    if (codes.length) {{
      html += "<table><thead><tr><th>响应码</th><th>说明</th></tr></thead><tbody>";
      codes.forEach(function (code) {{
        html += "<tr><td class='mono'>" + esc(code) + "</td><td>" + esc(responses[code].description || "") + "</td></tr>";
      }});
      html += "</tbody></table>";
    }}
    if (!html) html = "<p>无参数。</p>";
    return html;
  }}

  function render() {{
    var spec = state.spec;
    if (!spec) return;
    var ops = [];
    Object.keys(spec.paths || {{}}).forEach(function (path) {{
      Object.keys(spec.paths[path]).forEach(function (method) {{
        if (["get", "post", "put", "patch", "delete"].indexOf(method) < 0) return;
        var op = spec.paths[path][method];
        ops.push({{ path: path, method: method.toUpperCase(), op: op, group: groupOf(path, op) }});
      }});
    }});
    var needle = state.query.trim().toLowerCase();
    if (needle) {{
      ops = ops.filter(function (o) {{
        return (o.path + " " + o.method + " " + (o.op.summary || "") + " " + o.group).toLowerCase().indexOf(needle) >= 0;
      }});
    }}
    stat.textContent = ops.length + " 个端点";
    if (!ops.length) {{ list.innerHTML = "<div class='empty'>没有匹配的端点。</div>"; return; }}
    var groups = {{}};
    ops.forEach(function (o) {{ (groups[o.group] = groups[o.group] || []).push(o); }});
    var html = "";
    Object.keys(groups).sort().forEach(function (name) {{
      html += "<h2>" + esc(name) + " <span class='badge'>" + groups[name].length + "</span></h2>";
      groups[name].forEach(function (o) {{
        html += "<details class='op'><summary>" +
          "<span class='m m-" + o.method.toLowerCase() + "'>" + o.method + "</span>" +
          "<code class='path'>" + esc(o.path) + "</code>" +
          "<span class='sum'>" + esc(o.op.summary || "") + "</span></summary>" +
          "<div class='body'><p>" + esc(o.op.description || "无描述。") + "</p>" +
          paramsTable(o.op) +
          "<pre>curl -s http://127.0.0.1:8765" + esc(o.path) + "</pre></div></details>";
      }});
    }});
    list.innerHTML = html;
  }}

  fetch("/openapi.json").then(function (r) {{ return r.json(); }}).then(function (spec) {{
    state.spec = spec;
    render();
  }}).catch(function (err) {{
    stat.textContent = "加载失败";
    list.innerHTML = "<div class='empty'>无法读取 /openapi.json：" + esc(err) + "</div>";
  }});

  q.addEventListener("input", function () {{ state.query = q.value; render(); }});
}})();
</script>
</body>
</html>
"""


def render_html(title: str, version: str) -> str:
    """返回自托管文档页的 HTML。"""
    return _TEMPLATE.format(title=escape(title), version=escape(version))
