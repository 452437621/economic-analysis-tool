# EPIC V2 · 高保真交互原型

单文件、离线可用、无外部依赖的个人宏观—市场分析终端原型。深色为默认主题，浅色可切换；全部文案为简体中文，时间统一为北京时间，页面基准 1440×1000。

## 文件

| 文件 | 说明 |
| --- | --- |
| `index.html` | 唯一原型文件：HTML + CSS + 原生 JS + 内联 SVG，无字体/CDN/图片/网络请求 |
| `preview-compass.png` | 周期罗盘（深色） |
| `preview-history.png` | 世界长河（深色） |
| `preview-pipeline.png` | 透明管线（深色） |
| `preview-alerts.png` | 预警台（深色） |
| `preview-light.png` | 周期罗盘（浅色） |
| `preview-drawer.png` | 溯源抽屉打开态（深色） |

## 打开方式

直接双击 `index.html`（推荐 Chrome / Edge），或打开：

```text
file:///D:/Code/4_%E4%B8%AA%E4%BA%BA%E7%A0%94%E5%8F%91/economic-analysis-tool/docs/design/mockup-v2/index.html
```

无需构建、无需本地服务器、不访问网络。所有图表由内联 SVG 手绘，sprite 与图标全部内联。

## URL 参数

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `view` | `compass` / `history` / `pipeline` / `alerts` | 直达视图，默认 `compass`（周期罗盘） |
| `theme` | `dark` / `light` | 主题，默认 `dark` |
| `open` | `provenance` / `node` / `scenario` | 打开溯源抽屉 / 管线节点抽屉 / 定位反事实沙盘 |
| hash | `#compass` 等 | 与 `view` 等价；无 `?view` 时读取 |

示例：

```text
index.html?view=history
index.html?view=alerts&theme=light
index.html?view=compass&open=provenance
index.html?view=pipeline&open=node#pipeline
```

视图、主题切换会同步写回 URL，并保存到 `localStorage['epic-v2-prefs']`；刷新后保持上次视图与主题。`?open=node` 默认打开「周期引擎」节点详情。

## 已实现交互

### 全局

- 232px 侧边栏 + 56px 顶栏；面包屑随视图更新。
- 顶栏搜索（`Ctrl/⌘ + K`）打开命令面板：可跳转四个视图，也可执行切换主题、打开溯源、定位沙盘、编辑阈值、重置本地偏好；`↑/↓` 选择，`Enter` 执行，`Esc` 关闭。
- 主题按钮在深/浅色之间切换；Toast 停留 2.6s。
- 未上线导航（总览、简报、行情、利率、日历、国家矩阵、指标库、数据健康、模型卡、审计）显示「待接入」并给出 Toast，不跳空白页。
- 打印样式隐藏侧边栏、顶栏、抽屉与 Toast，仅保留正文。

### 周期罗盘（compass）

- 环形四象限罗盘：外圈置信度弧 73%，指针指向「滞胀」偏过热 20°；外圈方位标签为上「通胀↑」、下「通缩↓」、右「增长↑」、左「增长↓」，环内仍为四象限名。
- 五力仪表五条：债务/货币 82、内部冲突 68、外部冲突 61、自然冲击 34、技术革命 78；每条「为什么」打开对应溯源抽屉。
- 8 张关键读数卡，含单位、日变动、z-score、内联 sparkline 与「E2 证据」徽标。
- 今日预警 3 条，可打开溯源；历史类比 Top3（71% / 68% / 64%）打开抽屉「历史类比」页签。
- 溯源抽屉宽 560px，5 层折叠：结论、贡献分解、规则命中/反证、特征、原始数据；底部可复制引用、查看 SQL、导出 JSON、标记存疑；点击遮罩或 `Esc` 关闭。

### 世界长河（history）

- 时间窗 1500–2100 / 1700–2100 / 1900–2100；五个图层开关（帝国兴衰、储备货币、债务危机、战争与革命、技术革命）。
- 横向长河 SVG：荷兰/英国/美国/中国四条泳道，崛起—顶峰—衰落色带、关键年份事件、2026 虚线；储备货币示意面积曲线可开关。
- 缩放 − / 100% / ＋（100% 适配卡片，放大后可横向滚动）。
- 点击事件标记或泳道刷新右侧详情：事件名、年份、类型、影响、置信度 A/B/C、离线来源文本；下方周期对照表与历史规律 6 条。

### 透明管线（pipeline）

- 运行状态条：`RUN-2026-11-17-0712`、42.6s、96%、14/18、影子模型 R-2026.11。
- 横向 DAG 六节点，状态/耗时/行数/时间/错误数；点击节点打开右侧详情（输入、输出、SQL/HTTP 端点、日志 tail、版本）。
- 本次研判溯源静态 5 层树，默认展开 L1–L2。
- 反事实沙盘三个滑块（实际利率 ±100bp、美元 ±8%、央行购金 ±40%），按页面标注的演示公式实时改变结论强度与一句话；可重置。
- 模型卡：EPIC-C v2、14 序列、9 参数、2026-10 回测、Brier 0.19、失效条件 3 条。

### 预警台（alerts）

- 汇总条：3 高 / 5 中 / 7 低，未来 7 天 6 个日历事件（3 个三星）。
- 预警表 10 行，严重度筛选（全部/高/中/低）；列为严重度色点（红高/橙中/黄低）、名称、当前值、阈值、距离、历史触发后 20 日胜率、置信度、更新时间。
- 阈值编辑器：切换预警项、拖动阈值，实时显示当前值、距离、预计触发与影响资产；保存/恢复默认均有 Toast。
- 财经日历未来 7 天，含重要性星级、预期、前值、北京时间、影响资产 chips。

## 截图命令

六张图统一 `1440×1000`。本机 Chrome 命令行会在 PNG 落盘前返回，因此用 `Start-Process -Wait` 并对每次截图使用全新的临时 `--user-data-dir`：

```powershell
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$out    = 'D:\Code\4_个人研发\economic-analysis-tool\docs\design\mockup-v2'
$base   = 'file:///D:/Code/4_%E4%B8%AA%E4%BA%BA%E7%A0%94%E5%8F%91/economic-analysis-tool/docs/design/mockup-v2/index.html'

$shots = @(
  @('preview-compass.png', '?view=compass'),
  @('preview-history.png', '?view=history'),
  @('preview-pipeline.png','?view=pipeline'),
  @('preview-alerts.png',  '?view=alerts'),
  @('preview-light.png',   '?view=compass&theme=light'),
  @('preview-drawer.png',  '?view=compass&open=provenance')
)

foreach ($s in $shots) {
  $profile = Join-Path $env:TEMP ('epic-v2-' + [guid]::NewGuid().ToString('N'))
  Start-Process -FilePath $chrome -Wait -WindowStyle Hidden -ArgumentList @(
    '--headless=new', '--disable-gpu', '--hide-scrollbars',
    '--window-size=1440,1000', '--force-device-scale-factor=1',
    '--virtual-time-budget=4000', "--user-data-dir=$profile",
    "--screenshot=$(Join-Path $out $s[0])", ($base + $s[1])
  )
  Remove-Item $profile -Recurse -Force -ErrorAction SilentlyContinue
}
```

也可按任务书使用单条命令（若发现 PNG 未生成，改用上面的 `Start-Process -Wait`）：

```powershell
& 'C:\Program Files\Google\Chrome\Application\chrome.exe' --headless=new --disable-gpu --hide-scrollbars --window-size=1440,1000 --screenshot='docs\design\mockup-v2\preview-compass.png' 'file:///D:/Code/4_%E4%B8%AA%E4%BA%BA%E7%A0%94%E5%8F%91/economic-analysis-tool/docs/design/mockup-v2/index.html?view=compass'
```

| 截图 | 视口 | 说明 |
| --- | --- | --- |
| `preview-compass.png` | 1440×1000 | 周期罗盘深色首屏 |
| `preview-history.png` | 1440×1000 | 世界长河全时间窗 + 1971 事件详情 |
| `preview-pipeline.png` | 1440×1000 | DAG + 溯源树 + 沙盘 + 模型卡 |
| `preview-alerts.png` | 1440×1000 | 汇总、预警表、阈值编辑器、日历 |
| `preview-light.png` | 1440×1000 | 浅色主题周期罗盘 |
| `preview-drawer.png` | 1440×1000 | 溯源抽屉 5 层打开态 |

## 自检

- `index.html` 内无 `http://`、`https://`、`<script src`、`@import url(`、`<link` 外链。
- 内联 JS 通过 `node --check`；控制台无脚本报错。
- 1440 宽度下无横向滚动；≤1240 / ≤1024 有断点兜底（卡片改列、侧栏收窄、命令面板贴边）。
- 四个视图均可 `?view=` 直达，刷新保持；`Esc` 关闭抽屉与命令面板；两套主题均完整可用。

## 已知限制

- 全部数据为静态示例，数值按 2026-11-17 09:30 设定，不连接后端。
- 「反事实沙盘」为演示线性公式，页面已注明，非模型真实推理。
- 储备货币份额为示意曲线，非精确历史序列；历史事件来源为离线文本，链接不跳转。
- `?open=node` 固定打开「周期引擎」节点；其余节点需在 DAG 中点击。
- 对比历史类比、复制引用、下载 JSON 为纯前端行为；「标记存疑」仅切换按钮状态。
- 打印版仅保留正文卡片，交互态不打印。
