# EPIC 前端（Vue 3 + TypeScript + Vite）

## 运行

```powershell
# 仓库根目录
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1   # 构建到 ../web（由 FastAPI 托管）
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1 -NoBrowser

# 前端开发（单独终端；/api 代理到 127.0.0.1:8765）
cd frontend
npm.cmd run dev            # http://127.0.0.1:5173
npm.cmd run typecheck      # vue-tsc --noEmit
```

> 本机 `npm.ps1` 被执行策略拦截，必须用 `npm.cmd`。
> 本机 esbuild 偶尔无法删除系统临时目录文件：构建前设置 `$env:TEMP` 与 `$env:TMP` 到 `frontend/.tmp`（`scripts/build.ps1` 已处理）。

## 目录

```
frontend/src/
├─ api/            client.ts（fetch 封装）、types.ts（后端响应类型）、endpoints.ts（全部端点）
├─ components/
│  ├─ ui/          IconSprite / Drawer / Sparkline / EmptyState / ErrorState / SkeletonBlock / ToastHost
│  ├─ charts/      EChart.vue（ECharts 按需封装）
│  └─ domain/      CommandPalette / SettingsDrawer / AlertsDrawer / EvidenceDrawer / HistoryModal
├─ composables/    usePolling / useFormat / useClock / useToast(stores)
├─ layouts/        AppShell / Sidebar / Topbar
├─ stores/         prefs / health / alerts / evidence / history / toast（Pinia）
├─ styles/         app.css（设计系统：token + 组件样式，自 mockup 提炼）、tailwind.css
├─ utils/market.ts 快照分类、内外盘判定、宏观分组
└─ views/          Overview / Market / Rates / Analysis / Signals / Gold / Theses / Briefs / System
```

## 约定（新增页面必须遵守）

1. **只使用现有依赖**：vue / vue-router / pinia / echarts / vue-echarts / dayjs / markdown-it / dompurify / sortablejs / @vueuse/core / lucide-vue-next。不新增依赖、不引外部 CDN、不引外部字体。
2. **取数**：一律用 `@/api/endpoints` 中的函数 + `usePolling`（或 `onMounted` + 手动 refresh）。
   - 轮询间隔用函数形式读取设置：`interval: () => prefs.refreshInterval * 1000`（行情类）；低频数据用固定毫秒。
   - 错误不清空已有数据；单区块失败只渲染 `ErrorState`，不拖垮整页。
3. **格式化**：数字/价格/涨跌/时间一律用 `@/composables/useFormat`（`fmtPrice/fmtPct/fmtSigned/fmtInt/fmtTime/fmtDateTime/fmtMacro/trendClass/stars`）；不要在视图里自己 `toFixed` + 拼 `%`。
4. **样式**：优先复用 `app.css` 里已有的类（`.card/.card-head/.card-title/.card-sub/.card-body/.data-table/.btn/.badge/.seg/.opt/.chip/.toolbar/...`），可参考 `docs/design/mockup/index.html` 的对应视图结构与类名。视图内只写补充样式（`<style scoped>`），不要复制整段 mockup CSS。
5. **图标**：`<svg class="ic"><use href="#i-xxx" /></svg>`，可用 id 见 `components/ui/IconSprite.vue`（46 个）。
6. **主题**：颜色只用 CSS 变量（`var(--text/--muted/--dim/--accent/--up/--down/--surface/--border/--ok/--warn)`），不要写死 hex；红涨绿跌由 `--up-color/--down-color` 自动切换。
7. **交互**：点击标的名/价格打开历史走势：`useHistoryStore().openHistory('instrument', symbol, name)`；点击新闻/证据打开 `useEvidenceStore().show(documentId)`；提示用 `useToast()`。
8. **页面结构**：视图根元素 `<div class="view active">`；页面标题用 `.page-head > .page-eyebrow + .page-h1 + .page-sub`；区块标题用 `.sec-row/.sec-title/.sec-count/.sec-meta`。
9. **数据契约**：`src/api/types.ts` 是唯一来源；需要新端点时先补 `endpoints.ts`，但**不要改后端**。真实响应样本见 `data/_api-samples/*.json` 与 `skeleton.txt`（中文可能为乱码，仅字段结构可信）。
10. **验证**：写完后 `npm.cmd run typecheck` 必须通过；用 `npm.cmd run dev -- --port 517x` + Chrome headless 截图自检（1440×1000），检查无横向滚动、无文字截断、空态/加载态正常。
