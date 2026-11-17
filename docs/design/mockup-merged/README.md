# 合并版 UI 原型（V2 壳 + V1 内容）

把两版设计原型合并为一份可直接交付评审的 V2 原型：

- 壳层（导航 / 顶栏 / 主题 / 命令面板 / 路由）：`../mockup-v2/index.html`
- 内容（总览 / 行情 / 简报 / 设计规范）：`../mockup/index.html`

产物：**`index.html`**（单文件，约 340 KB，无外链、无 CDN、无外部字体）。

打开方式：直接用浏览器打开 `index.html` 即可（支持 `?view=overview|brief|market|compass|history|pipeline|alerts|tokens`，
`theme=dark|light` 覆盖主题）。

## 合并策略（为什么这样做）

两版原型的 CSS 都使用 `.card` / `.kpi` / `.badge` 这类**同名类**，直接拼进一个文档会互相覆盖。
因此采用「**V2 为壳 + V1 内容以 Shadow DOM 隔离挂载**」：

1. 用 Chrome headless `--dump-dom` 抓取 V1 页面**渲染后的 DOM**（V1 的关注列表、热力图、行情表、会员持仓等区块
   都是加载时由 JS 生成的，抓静态源文件只能得到空容器）。
2. 把 V1 的四个视图内部 HTML 存进 `<template id="v1-tpl-*">`。
3. V1 的全局 CSS 做一次改造（`:root` 交由外层主题接管，`body` → `.v1-page`，`html[data-theme=...]` →
   `.v1-page[data-theme=...]`），存进 `<script type="text/plain" id="v1-css">`。
4. 首次切换到某个 V1 视图时，`mountV1()` 在挂载点上 `attachShadow`，把样式、图标 sprite（V1 原有 46 个
   `symbol`）和冻结的 DOM 一起注入 shadow root。
   - V2 的样式不会漏进 V1 页面，V1 的样式也不会污染 V2 页面；
   - 主题切换（深色/浅色）通过 `MutationObserver` 同步到 shadow 内 `.v1-page[data-theme]`；
   - V1 页面里带 `data-go="brief"` 的链接被劫持为视图跳转。

## 视图清单（8 个）

| 分组 | 视图 | 来源 | 说明 |
|---|---|---|---|
| 今日 | 总览 | V1 | 今日主线 hero、四张状态卡、重点关注、跨资产热力图、利率快照、告警、财经日历 |
| 今日 | 简报 | V1 | 目录 + 正文（5 节、证据 E-01…E-04）+ 本期概览 + 关联证据 |
| 市场 | 行情 | V1 | 35 个品种分组表、会员持仓 Top20、数据质检提示 |
| 研判 | 周期罗盘 | V2 | 相位角罗盘、五力仪表、关键读数、今日预警、历史类比 |
| 研判 | 世界长河 | V2 | 1500–2100 时间轴、帝国兴衰与储备份额、周期对照、历史规律 |
| 研判 | 透明管线 | V2 | 采集→质检→特征→周期→情景→输出 DAG、溯源分层抽屉、反事实沙盘 |
| 研判 | 预警台 | V2 | W1–W12 规则、阈值编辑、政治日历 |
| 系统 | 设计规范 | V1 | 色板/字阶/按钮/表单/表格/反馈状态等 Design Tokens |

## 已知差异（有意保留）

- **数据日期不同**：V1 内容冻结在它自己的设计快照（2026-11-13），V2 视图的数据时点徽标为 2026-11-17；
  V1 的日期文案不再改写，避免在评审时误以为已接入真实新数据。
- **V1 页内按钮是静态的**：刷新、导出、复制、筛选、切换主题等只保留视觉效果（`data-go` 跳转除外）；
  V2 壳层的搜索（Ctrl K）、主题切换、视图跳转、溯源抽屉、沙盘、阈值滑杆是可交互的。
- **V1 浅色主题**：shadow 内已带浅色 token 覆盖，深浅两套均已截图验证；个别 V1 专用装饰渐变按浅色 token 呈现。
- 侧栏「利率 / 日历」仍是「待接入」占位（两版都没有对应设计稿），不伪造页面。

## 重新生成

```powershell
# 1) 抓取 V1 渲染后 DOM（约 220 KB，含 chrome stderr 前缀，脚本会自动从 <!DOCTYPE html> 起截取）
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --disable-gpu `
  --virtual-time-budget=8000 --user-data-dir=<临时 profile 绝对路径> --dump-dom `
  "file:///D:/.../docs/design/mockup/index.html" 2>&1 | Out-File -Encoding utf8 data\_v1_dom.html

# 2) 合并
& .venv\Scripts\python.exe docs\design\mockup-merged\build.py
```

`build.py` 中的路径以本机绝对路径书写，迁移到其他机器时改脚本顶部的 `ROOT` 即可。产物始终写入
`docs/design/mockup-merged/index.html`，**不会覆盖两版原始原型**。

## 验收截图

深色：总览 / 行情 / 简报 / 周期罗盘 / 世界长河 / 透明管线 / 预警台 / 设计规范。
浅色：总览 / 行情 / 简报 / 设计规范 / 周期罗盘。

各视图在 1440×1500 下均无横向滚动条；V1 内容与 `../mockup/preview-*.png` 视觉一致，V2 视图与
`../mockup-v2/preview-*.png` 一致，差异仅限壳层导航与标题。
