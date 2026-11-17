# TradingEconomics 竞品标杆研究（面向 EPIC 个人宏观-市场分析工具）

> 研究对象：中文站 <https://zh.tradingeconomics.com/>（英文主站 <https://tradingeconomics.com/>）
> 抓取时间：页面所示时间为 2026-11（站点数据已同步到该日期，本文按「页面所示」引用）
> 方法：对页面做 HTTP 抓取 + 逐页比对，并交叉核对官方 API 文档（docs.tradingeconomics.com）中的字段定义。
> 未核实项：凡标「未核实」者，为页面表格由前端 JS 异步渲染、静态抓取拿不到表格体，或需要登录/付费账号才能验证。

---

## 0. 三条一句话结论

1. **TE 的产品本质是「指标库 + 日历 + 行情」三套数据共用一个壳**：页面骨架几乎不区分数据类型，所有实体都被压成「名称 + 现值 + 前值 + 极值 + 单位 + 参考日期」这一种卡片形状，因此页面可以批量生成、URL 可以按 `国家/指标` 规则推导。
2. **它的护城河不是 UI，而是「叙事 + 结构化数据」的粘连**：指标详情页把一段人写的编辑摘要、一句统计结论、日历、Te 指标卡、同族指标、新闻串在同一个页面，用户一次停留就能完成「读数—看懂—看下次什么时候发」的闭环。
3. **它的免费/付费边界非常粗暴且有效**：日历的「下周/下月/昨天」直接加锁、数据下载入口加锁、API 无免费档；个人本地工具不应复制这种「阉割式付费墙」，但应复制它「把付费点放在历史区间与批量导出，而不是放在看一眼现值」的取舍。

---

## 1. 信息架构与页面清单

### 1.1 一级导航（实测 7 项）

| 导航 | 路径 | 解决什么问题 |
| --- | --- | --- |
| 日历 | `/calendar` | 未来/近期有哪些数据要发布、发出来是多少、市场预期多少 |
| 新闻 | `/stream` | 事件流的文字解释（按时间倒序的新闻流） |
| 市场（下拉 8 项） | `/commodities`、`/stocks`、`/shares`、`/currencies`、`/crypto`、`/bonds`、`/earnings`、`/holidays` | 行情快照：价格、涨跌、周期涨跌幅 |
| 指标 | `/indicators` | 指标目录（按 14 个主题分组的指标全集，每行指向 `/country-list/{indicator}`） |
| 国家 | `/countries` | 国家目录与地区入口 |
| 预测（下拉 7 项） | `/forecast/commodity`…、`/forecasts`、`/indicators?g=forecast` | 机构自研模型的预测值 |
| （页脚）评级 | `/country-list/rating` | 主权信用评级与 TE 评分 |

二级/三级导航结构：**国家 → 指标分组 → 指标详情**，以及 **指标 → 国家横向对比列表**。两套路径互为逆向，同一份数据既可从「国家视角」也可从「指标视角」进入，这是它最重要的 IA 决策。

- `/indicators` 的主题分组（实测）：主要指标、市场、劳动力、政府、价格、金融、贸易、国内生产总值、住房、商业、消费、税种、健康、气候、能源。分组内是纯链接列表，每个链接形如 `/country-list/gdp-growth-rate`。
- `/country-list/{indicator}` 顶部是洲际标签：世界 / 欧洲 / 美洲 / 亚洲 / 非洲 / 大洋洲 / G20（`?continent=` 参数），用来做「同一指标跨国排序」。
- 国家页 `/united-states/indicators` 内部用锚点再分 12 组：概述、国内生产总值、劳动力、价格、金融、贸易、政府、商业、消费、住房、能源、健康。

### 1.2 页面清单（逐一实测）

| 页面 | 路径 | 解决的问题 | 典型交互 |
| --- | --- | --- | --- |
| 首页 | `/` | 30 秒概览：头条新闻 + 6 组行情 | 主题切换、语言切换、行情「更多」跳转 |
| 国家指标总览 | `/united-states/indicators` | 一个国家所有关键指标的横向快照 | 锚点跳转；每行下钻到指标详情 |
| 指标详情 | `/united-states/inflation-cpi` | 单个指标的一切：叙事、历史、日历、预测、新闻 | 页内锚点（摘要/统计数据/预测/市场预期值/日历/下载）、国家切换下拉 |
| 指标跨国列表 | `/country-list/inflation-rate` | 同一指标在约 200 国间的排序与横向对比 | 洲际筛选、列排序（未核实是否支持点击列头排序） |
| 日历 | `/calendar`、`/united-states/calendar` | 发布日程与结果 | 时间范围、重要性、国家多选、时区、导出 |
| 行情 | `/commodities`、`/stocks`、`/currencies`、`/crypto`、`/bonds`、`/shares` | 价格快照 | 视图切换标签（见 §5） |
| 行情视图 | `/stocks/geomap`、`/stocks/treemap`、`/stocks/scatter`、`/stocks/correlations` | 空间/结构/相关性视角 | 时间窗切换：日常/每周/每月/每年/YTD（英文站为 Daily/Weekly/Monthly/YTD/YoY） |
| 预测 | `/forecasts`、`/forecast/{asset}`、`/indicators?g=forecast` | 中期与长期预测 | 资产类别下拉；国家预测表 |
| 评级 | `/country-list/rating` | 主权评级对照 | 洲际筛选；评级映射表 |
| 国家评级历史 | `/{country}/rating`（如 `/ghana/rating`） | 单一国家的评级变动史 | 表格：机构 / 评级 / 展望 / 日期 |
| API 文档 | `docs.tradingeconomics.com` | 字段字典与限制 | 左侧树形目录、Python/JS/C# 多语言示例 |

### 1.3 「下钻」是它唯一真正的交互范式

没有任何「工作台/看板自定义」功能（未核实是否存在会员版自定义面板）。用户路径永远是：概览 → 分组 → 单指标 → （可选）跨国对比或新闻。**没有对比视图、没有自选组合、没有告警规则编辑器**——告警只有一种：浏览器通知，文案为「Notifications — Alerts for major calendar releases, even when this tab is minimised or in the background」，即仅针对重要日历事件的桌面通知，无阈值告警。这一点对我方产品是关键空白。

---

## 2. 核心数据模型

字段定义以官方 API 文档为准（口径比页面更完整），页面展示是其子集。

### 2.1 Indicator（指标，官方 snapshot 返回 21 个字段）

来源：<https://docs.tradingeconomics.com/indicators/snapshot/>

| 字段 | 含义 | 粒度/示例 |
| --- | --- | --- |
| `Country` / `Category` / `Title` | 国家、指标英文名、展示标题 | Mexico / Balance of Trade |
| `LatestValue` + `LatestValueDate` | 最新值与其参考日期 | -1377.09 / 2023-08-31 |
| `PreviousValue` + `PreviousValueDate` | 前一次发布的值与日期 | -881.2 / 2023-07-31 |
| `HighestValue`/`HighestValueDate`、`LowestValue`/`LowestValueDate` | 全历史极值及其发生时间 | 2158.77 / 2020-07-31；-5559.0 / 2014-10-31 |
| `Unit` | 单位，字符串且不统一 | `%`、`USD Million`、`Thousand Units`、`MXN Million` |
| `Frequency` | 频率 | Monthly / Quarterly / Yearly / Daily |
| `Adjustment` | 季调口径 | NSA（文档示例全为 NSA） |
| `Source` / `SourceURL` | 数据发布机构及其官网 | Banco de México / http://www.banxico.org.mx |
| `CategoryGroup` | 主题分组，用于页面的 12 组锚点 | Trade / Money / Prices |
| `HistoricalDataSymbol` | 序列代码（跨 API/Excel 的稳定 ID） | MXTBBAL |
| `CreateDate` / `FirstValueDate` | 入库时间 / 序列起点 | 2014-07-25 / 1980-01-31 |
| `URL` | 站内详情页路径 | `/mexico/balance-of-trade` |

关键观察（对建模很重要）：

- **没有「同比/环比」字段**。TE 把「通胀率（年）」和「月度通货膨胀率」当成**两个独立指标**（`/country-list/inflation-rate` 与 `/country-list/inflation-rate-mom` 各自成页）。这是「一个指标 = 一条序列」的扁平化建模，牺牲表达力换取实现简单。
- **没有 revision 字段**。修订只在日历事件层体现（见 2.2 `Revised`），指标层的 `PreviousValue` 已被修订后的值覆盖。
- **没有发布延迟字段**，只有市场行情的 `frequency: Live/Delayed`（见 2.4）。宏观指标的「延迟」只能靠日历的发布时间间接体现。
- **单位是自由文本**，不是枚举——这直接导致页面无法自动做单位换算或跨指标计算。

### 2.2 Calendar event（日历事件，官方 schema 返回 24+4 个字段）

来源：<https://docs.tradingeconomics.com/economic_calendar/schema/>

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| `CalendarID` | 事件唯一 ID | 87220 |
| `Date` | 发布时刻（UTC） | 2016-12-02T13:30:00 |
| `Country` / `Category` / `Event` | 国家、原始分类、事件名 | United States / 20 Year Bond Yield / 20-Year Bond Auction |
| `Reference` / `ReferenceDate` | 数据所指周期的简称/精确日期 | Nov/26 / 2016-11-30 |
| `Actual` | 最新发布值 | 178K |
| `Previous` | 上次值，**已含修订** | 142K |
| `Revised` | 上次发布时报告的原值（修订前） | 161K |
| `Forecast` | 经济学家共识预期 | 175K |
| `TEForecast` | TE 自家模型预测 | 180K |
| `Importance` | 1=低 / 2=中 / 3=高 | 3 |
| `DateSpan` | 0=时间确定，1=时间估计 | 0 |
| `Source` / `SourceURL` | 发布机构与官网 | U.S. Bureau of Labor Statistics / dol.gov |
| `Currency` / `Unit` / `Ticker` / `Symbol` / `URL` | 币种、单位、代码、站内详情 | C$ / % / NFP TCH / IJCUSA / /united-states/non-farm-payrolls |
| `LastUpdate` | 该行最后更新时间 | 2016-12-02T13:31:00 |
| `values=true` 时追加 | `ActualValue`/`PreviousValue`/`ForecastValue`/`TEForecastValue` 数值型 | 178000 |

这是全站设计最成熟的一张表：**同一行同时容纳 4 个数值口径（actual / consensus / previous / revised）+ 1 个自家预测 + 精度标记（DateSpan）+ 来源与单位**。注意 `Forecast` 与 `TEForecast` 是两个不同字段，页面上会分列，这是它能同时服务「看市场预期」和「看自家观点」两种需求的原因。

### 2.3 Forecast（预测）

来源：<https://docs.tradingeconomics.com/forecasts/indicators/>

| 字段 | 说明 |
| --- | --- |
| `q1`…`q4` + `q1_date`…`q4_date` | 未来 4 个季度预测值及对应季末日期 |
| `YearEnd` / `YearEnd2` / `YearEnd3` | 当年末、次年末、第三年末预测 |
| `ForecastLastUpdate` | 预测生成时间（示例：2023-10-01T15:33:00） |
| `LatestValue`/`LatestValueDate`、`Frequency`、`Unit`、`HistoricalDataSymbol` | 与实际值对齐用的上下文 |

**6 个时间点 + 1 个生成时间戳，没有任何置信区间/概率字段**。呈现上，指标详情页把它写成一句话：「本季度末 3.40%；2027 年 2.60%，2028 年 2.50%，来源：TE 全球宏观模型和分析师预期」。

### 2.4 Market instrument（行情）

来源：<https://docs.tradingeconomics.com/markets/snapshot/>

字段：`Symbol`（如 `DCE:COM`）、`Ticker`、`Name`、`Country`、`Date`、`State`（CLOSED/OPEN）、`Last`、`Close`、`CloseDate`、`Group`（Livestock/Metals/Industrial）、`URL`、`Importance`（示例恒为 1000，用途未核实）、`DailyChange`/`DailyPercentualChange`、`WeeklyChange`、`MonthlyChange`、`YearlyChange`、`YTDChange`（各带 `*PercentualChange`）、`day_high`/`day_low`、`yesterday`/`lastWeek`/`lastMonth`/`lastYear`/`startYear`、`allTimeHigh`/`allTimeHighDate`、`allTimeLow`/`allTimeLowDate`、`decimals`、`unit`（`USD/T`、`CNY/T`）、`frequency`、`StartDate`、`LastUpdate`。

- `frequency` 实测取值包含 **`Daily`、`Delayed`**（是否为 `Live` 未核实）。
- 站方免责声明（原文可查）：「our financial market data is aggregated from a diverse range of third-party providers… on an 'as is' basis without any warranties and some of our market-related methods are under heavy development」。

### 2.5 Rating（主权评级）

- 列表页列：**Country | S&P | Moody's | Fitch | DBRS | TE 分数**；TE 分数为 0–100 的数值分（实测：澳大利亚 100、美国 97、日本 90、意大利 62、巴西 43、阿根廷 12）。
- 单国历史页（如 `/ghana/rating`）列：**机构 | 评级 | 展望 | 日期**，按时间倒序，可看到同一机构多次调整及其展望（Stable/Negative/Positive/Under Review/N/A）。
- TE 分数与三大机构等级的映射表是公开的（示例）：100 AAA/Aaa、95 AA+/Aa1、90 AA/Aa2、85 AA-/Aa3、80 A+/A1、75 A/A2、70 A-/A3、65 BBB+/Baa1、60 BBB/Baa2、55 BBB-/Baa3、50 BB+/Ba1、45 BB/Ba2、40 BB-/Ba3、35 B+/B1、30 B/B2、25 B-/B3、20 CCC+/Caa1、15 CCC/Caa2、10 CCC-/Caa3、5 C、0 D，并配 Prime / High grade / Upper medium grade / Lower medium grade / Non-investment grade / Highly speculative / Substantial risks / In default 等描述档。
- TE 自述方法论（外部引用其页面原文）：「scores the creditworthiness of a country between 100 (riskless) and zero (likely to default)… our ratings are based on a forward-looking macro-economic model which takes into account several leading economic indicators, financial market indicators」；并称「unsolicited and we are not paid in any way」，即非委托评级。
- **没有置信度 / 没有评级主体分歧标注**，四家评级并列在同一行由用户自行解读。

---

## 3. 「Te 指标卡」的确切构成

指标详情页 `/united-states/inflation-cpi` 的实测卡片（一行 8 列）：

| 现值 | 前次数据 | 最高 | 最低 | 日期 | 单位 | 频率 | 季节性调整 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3.70 | 3.40 | 23.70 | -15.80 | 1914 - 2026 | % | 每月一次 | NSA |

对应字段关系：`LatestValue` / `PreviousValue` / `HighestValue` / `LowestValue` / `FirstValueDate–LatestValueDate` 区间 / `Unit` / `Frequency`(本地化文案) / `Adjustment`。

- **卡片只给 8 个字段**，刻意不放 `Source`（来源放在页面正文与日历行里）。对我方的启示：卡片是「快照」，来源属于「可追溯性」，二者应在不同层级出现，避免卡片被噪声塞满。
- 详情页整体顺序（实测 12 段）值得原样借鉴：① 标题 + 编辑摘要段 → ② 一句话统计结论（含「从 X 升到 Y；1914–2026 平均 3.29%，最高 23.70%(1920-06)，最低 -15.80%(1921-06)」）→ ③ 预测句（含季末/两年后 + 来源）→ ④ 日历表（含**未发布的未来行**）→ ⑤ 相关子指标表 → ⑥ 同族指标表 → ⑦ 指标口径说明（CPI 篮子权重：食品 14%、能源 8%、商品 21%、服务 57%；服务再分住房 32%、医疗服务 7%、交通服务 6%）→ ⑧ Te 指标卡 → ⑨ 跨国列表跳转 → ⑩ 相关新闻 3 条 → ⑪ 页尾指标索引 → ⑫ 国家切换下拉。
- 「② + ③」的写法是最低成本的高价值设计：把统计极值和预测包成一句人话，无需用户看图。

---

## 4. 日历（Calendar）设计

### 4.1 行结构与数值口径

- 指标详情页内嵌的日历表列：**日历 | GMT 时间 | 参考日期 | 现值 | 前次数据 | 市场预期值**；未发布行留空（实测可见 2026-12-10 13:30 的未来行）。
- 全站日历（`/calendar`）的行内容未核实（表格体前端渲染，静态抓取只能拿到筛选控件），按官方 schema 应含 actual/consensus/previous/revised/TEForecast 五口径。
- **修订是显式字段而非隐藏差异**（`Revised` = 上次发布时报告的原值，`Previous` = 修订后值）。这一点比多数竞品诚实，也是我方可直接照搬的口径。

### 4.2 importance 星级

- 三档：1=低、2=中、3=高。页面上以复选方式筛选（`setCalendarImportance('1'|'2'|'3')`），**默认只勾选 1★**（即默认视图信息量最小、只剩低影响事件——这个默认值本身是个设计缺陷，详见 §7）。
- 中文站把该筛选按钮机翻成「碰撞」（原文 Importance），是本地化质量问题，不构成设计参考。

### 4.3 时区

- 下拉覆盖 **UTC-12 至 UTC+14** 逐项，含半小时/45 分钟时区（UTC+3:30、+4:30、+5:30、+5:45、+9:30、+10:30），**默认 UTC**。
- 这是全站少数「为全球用户认真做」的控件；个人工具若只服务本地用户，可简化为「UTC / 本地时区」二元切换。

### 4.4 筛选与导出

- 时间范围：最近 / 今天 / 明天 / 本周（默认「最近」）；**下周、这个月、下个月、昨天、上星期、前一个月带锁图标**，未登录时由前端 `if (!isLoggedIn)` 显示锁；另有自定义日期区间（openCustomDates）。
- 国家筛选：大列表多选，默认勾选一批主要经济体 + G20/G7/IMF 等组织；快捷组为 全部 / 主要的 / 非洲 / 美洲 / 亚洲 / 欧洲；带 擦除 / 关 / 保存。
- 导出：右上角日历下载区（`calendar-download`）+ From/Until 自定义区间提交表单；官方另提供 iCalendar 导出接口（<https://docs.tradingeconomics.com/economic_calendar/icalendar/>）与日历文案翻译接口（`/economic_calendar/translations/`）。

### 4.5 影响说明

- 未见「该数据发布为什么重要」的行内说明；解释性内容被放在**指标详情页的编辑摘要与口径说明段**。即：日历负责「什么时候发」，详情页负责「为什么重要」——用页面跳转替代弹层说明，这是一个可商榷的取舍。
- 中文站存在明显机翻（「碰撞」「分享」= Shares、「指数」「分散」= Scatter），可作为反面教材：**术语表必须先于翻译**。

---

## 5. 可视化与 UI 模式

### 5.1 行情区的 7 个视图标签（一套数据多视角）

`报价 | 地图(/stocks/geomap) | 树状图(/stocks/treemap) | 散点(/stocks/scatter) | 相关性(/stocks/correlations) | 预测(/forecast/stock-market)`，商品区另有 `相关性` 与 `预测`。

- 地图页的地区筛选：世界 / 欧洲 / 北美 / 南美 / 亚洲 / 非洲 / 大洋洲；时间窗：日常 / 每周 / 每月 / 每年 / YTD。
- 树状图与地图共用同一时间窗枚举（Daily/Weekly/Monthly/YTD/YoY），即「颜色 = 该窗口涨跌幅」的统一视觉语言。
- 相关性视图存在，但具体呈现未核实（需渲染后查看）。

### 5.2 图表与数据表

- 指标详情页提供历史曲线（页面「统计数据」锚点区，具体图表库与交互未核实）。
- 表格密度高：国家页 12 个分组、每组同样 7 列；行情表每屏 14 行 + 「更多」链接；纯文本表格、无斑马纹与悬浮卡片，靠行高与分隔线解决可读性。
- 数字格式：行情保留 5 位有效小数（EURUSD 1.10084、原油 85.056），指标按 `decimals` 字段显示；涨跌用正负号 + 百分比并列（`0.66 / -0.77%`），未见红绿配色证据（未核实颜色语义，仅确认中文站提供 Light/Dark/System 三档主题）。

### 5.3 排版与主题

- 顶栏：导航 + 语言（13 种语言：en/es/pt/fr/de/it/pl/id/ru/tr/ar/zh/jp/ko）+ Light/Dark/System + Apps 入口 + 登录。
- 页脚：Indicators / Solutions / About 三段式 + App 下载 + 13 语言列表 + 版权。
- 视觉风格：白底、深蓝强调色、无衬线；以信息密度取胜，不做视觉装饰。适合「工具型」定位，不适合「内容型」定位。

### 5.4 移动端

- 提供 iOS / Android App（App Store id1142178921、`com.tradingeconomics.calendar`）。网页端响应式适配**未核实**（无法在本次抓取中验证断点行为）。

### 5.5 付费墙与免费额度边界（实测证据）

| 能力 | 免费（未登录） | 需付费/会员 | 证据 |
| --- | --- | --- | --- |
| 指标现值、极值、单位、频率 | ✅ | — | 国家页与指标详情页完整可读 |
| 指标历史曲线 | ✅（页面可见） | 下载受限 | 页面「下载」锚点存在；官方称「Download historical data… using your browser」为会员能力 |
| 日历「最近/今天/明天/本周」 | ✅ | — | 下拉项无锁 |
| 日历「下周/本月/下月/昨天/上周/上月」 | ❌ 锁 | — | 🔒 图标 + `!isLoggedIn` 逻辑 |
| 数据批量导出（CSV/JSON/XLSX） | ❌ | Basic 起 | 会员页「Easy Export」 |
| 预测查看 | ❌（页面公开句为示例） | Basic 起（第三方复核称「forecast viewing 属最低档」） | 见 §8.2 |
| API | ❌ 无免费档 | Standard 起（含 500 请求/月） | 见 §8.2 |
| 日历 API / 实时流 / 再分发 | ❌ | Enterprise 起 | 见 §8.2 |

即：**「看现值免费、看历史区间与批量数据收费、看实时与自动化收费」**——这条边界与我方「个人本地工具、数据本地留存」的定位正好互补（我方本就不卖数据）。

---

## 6. 预测与评级的方法论与呈现（含对账）

### 6.1 预测：谁的预测、几个时间点、如何呈现

- 出处：**TE 自有全球宏观模型 + 分析师预期**。官方原句：「Trading Economics forecasts are built using a proprietary global macro model that takes into account our analysts' expectations, correlations between countries, and a set of logical relationships between different indicators.」（<https://docs.tradingeconomics.com/forecasts/indicators/>）
- 时间点：未来 4 个季度 + 当年末 + 次年末 + 第三年末（字段 `q1..q4`、`YearEnd`、`YearEnd2`、`YearEnd3`）；页面叙事里出现到「2027 年 2.60%、2028 年 2.50%」这样的年度粒度。
- 呈现方式：**没有图表化的预测置信带**。只有一句自然语言 + 详情页的预测锚点区 + 预测列表页的表格。置信度字段不存在，区间不存在，样本外误差也不存在。
- 与实际值的对账：**站内没有「预测 vs 实际」的历史准确率页面**（未核实是否存在会员版；公开页面未见）。日历层的 `TEForecast` 与实际 `Actual` 同列，构成「事后可自行对账」的原始素材，但 TE 不替用户算误差。

### 6.2 评级

- 谁做：S&P、Moody's、Fitch、DBRS 四家机构 + TE 自有 0–100 模型分。
- 如何展示：一行四列机构字母等级并排 + TE 数值分；单国页给出机构 / 评级 / 展望 / 日期 的完整变更史。
- 置信度：无。分歧处理：并列展示，不做加权或共识合成（TE 分数是另一套模型，不是四家的平均）。
- 对账：无。

**结论：TE 在「预测」这件事上只交付点估计，把解释权和可信度判断完全交给用户。** 这对我方是明确的差异化空间：个人工具完全可以做「季度预测 vs 实际」的对账表与滚动误差统计，成本很低而价值明显。

---

## 7. 数据源与授权（事实描述）

### 7.1 数据来源

- 宏观指标：各国统计机构与央行（字段 `Source`/`SourceURL` 逐条标注，示例：U.S. Bureau of Labor Statistics、Banco de México、INEGI）。
- 行情：聚合自多家第三方数据商，站方明示「aggregated from a diverse range of third-party providers… on an 'as is' basis」，并建议「如需官方数据请联系相应交易所」。
- 覆盖口径的自我描述在站内不一致（这是需要注意的事实）：会员页称「20 Million Indicators for 196 countries」；文档称约 300,000 条序列；条款页另有 232 国/200,000 指标的说法（第三方复核记录，见 §8.2 引用）。其中 2000 万条的大部分是 COMTRADE 双边贸易记录。

### 7.2 API 定价与限额

**硬限制（官方文档，可直接引用）** <https://docs.tradingeconomics.com/get_started/rate-limits/>

| 限制项 | 数值 |
| --- | --- |
| 历史数据单次调用行数上限 | 10,000 行 |
| 经济日历单次调用行数上限 | 1,000 行 |
| 单次调用 URL 长度上限 | 260 字符 |
| 请求速率 | 5 请求/秒（相邻请求至少间隔 200 ms） |

**档位（站点定价表为动态渲染，未能直读；以下为第三方复核 + 搜索引擎快照，标「待复核」）**
- Basic / Standard / Professional / Enterprise 四档；API 从 Standard 起，Enterprise 才含日历 API、实时流、白标与再分发。
- 第三方复核（2026-10 更新）：Basic ≈ $29.99/月（无 API、无导出）；Standard ≈ $199/月（500 请求 + 500 次序列导出/月）；Professional ≈ $399/月（5,000 请求/导出、批量下载、新闻与 MCP）；年付约 25% off、季付 15% off。搜索引擎快照另见 $22/月（年付）与 $29/月（月付）、Standard $149、Professional $299 的不同版本 —— **价格随时间与计费方式变动，采购前须以官网为准（待复核）**。
- 试用：1 周试用费 $4.99 / $49 / $99（按档位），且 **「trial users are limited to 100000 data points and 100 requests for data」**、不可退款、到期自动转正式订阅（此段为站内原文，可直接引用）。
- 再分发：官方条款授予「limited, personal, nontransferable, revocable licence to analyse the data」，面向客户的再分发需 Enterprise 商务洽谈；「pricing is adjusted to the distribution you make」。

> 对我方的含义：**不存在可合法内嵌 TE 数据做个人工具免费分发的通道**。数据必须自采（官方统计机构 / FRED / World Bank / 各国统计局），TE 只做设计参考，不做数据源。

---

## 8. 对我方工具的启示

### 8.1 值得抄的 10 个设计

1. **「指标卡」固定 8 字段**（现值/前值/最高/最低/日期区间/单位/频率/季调）。理由：一张卡就能回答「现在多少、比上次如何、历史上什么位置」，字段少所以批量渲染与移动端都好做；且与我方 SQLite 单表结构几乎一一对应。
2. **双向 IA：国家→指标 与 指标→国家**。理由：同一份数据两套入口，用户既能「看美国发生了什么事」，也能「看全球通胀谁最高」，无需两套数据表。
3. **日历事件五口径并列**（Actual / Consensus / Previous / Revised / TEForecast）+ `DateSpan` 时间精度标记 + `Importance` 1–3。理由：这是信息密度与可解释性的最佳配比；`Revised` 显式化尤其值得抄，多数工具把修订藏在「前值已更新」里，用户无法发现修订。
4. **把统计结论写成人话**（「从 3.40% 升到 3.70%；1914–2026 平均 3.29%，最高 23.70%(1920-06)」）。理由：不需要图表就能定位数据在历史中的位置，纯靠模板字符串即可生成，成本极低、感知极强。
5. **指标详情页 = 叙事 + 日历（含未来行）+ 统计卡 + 同族 + 新闻 的聚合页**。理由：一次停留完成「读数—看懂—下次何时发」的闭环，减少跳转；未来行让用户知道「这个指标下次什么时候更新」。
6. **指标口径说明段（如 CPI 篮子权重）**。理由：宏观数据最大的坑是口径误读（同比 vs 环比、季调 vs 未季调），把口径写在卡片旁边能显著降低误判；我方可用 Markdown 字段维护。
7. **`Source` + `SourceURL` 逐条可追溯**。理由：个人研究工具最需要「这个数字谁发的、原文在哪」，而 TE 的 API 字段已证明该设计可行且成本低。
8. **稳定的序列代码 `HistoricalDataSymbol`**。理由：显示名会变、国家名会中英混用，必须有稳定 ID 才能做本地增量抓取与去重；我方应立即在 schema 里加 `series_key`。
9. **一套数据多视图 + 统一时间窗枚举**（报价/地图/树状图/散点/相关性/预测，时间窗统一为日/周/月/YTD/年）。理由：视觉语言一致，用户学一次即可切换视角；我方只需先做「表格 + 折线 + 国家热力」三视图并统一时间窗。
10. **明确的数据免责声明与「as is」措辞**。理由：行情为第三方聚合，声明可降低预期、避免误导；个人工具虽不对外发布，但本地界面仍需标注「数据来源/延迟」，以便自己回看时判断可信度。

### 8.2 不该抄 / 不适合个人本地工具的 5 个设计

1. **日历时间范围的「锁」式付费墙**（下周/下月/昨天直接锁）。理由：个人本地工具没有会员体系，锁只会锁住自己；且把「昨天」锁住会让回看功能失效 —— 应全量开放。
2. **importance 默认只勾 1★**（默认视图只剩低影响事件）。理由：实测的默认值会让首屏几乎无信息，是明显的默认值错误；我方应按 `importance >= 2` 且「本周」为默认。
3. **无置信区间的点预测**（TE 只给 q1–q4 与 YearEnd1–3）。理由：个人工具的价值恰在「我的预测错在哪」，应存预测快照并计算滚动误差，而不是复制点估计。
4. **自由文本 `Unit` + 「同比/环比各自成指标」的扁平建模**。理由：个人工具数据量小，完全有条件做 `unit` 枚举 + `transformation`(yoy/mom/level) 维度，从而支持「同一指标换口径看图」；照抄扁平化会导致指标数膨胀数倍。
5. **13 语言 + 4 家评级机构 + 196 国全量覆盖的广度**。理由：个人工具维护不动这么多数据源，广度只会带来抓取失败与空值；应收敛到「中/美/欧/日 + 主要商品与汇率」的窄深覆盖，把精力放在口径正确与对账上。

（另有一条不算「设计」但必须避开的坑：中文站大量机翻错误——「碰撞」= Importance、「分享」= Shares、「分散」= Scatter。**术语表要先于翻译落地**，我方界面文案应显式维护一份「宏观术语中英对照」。）

---

## 9. 参考链接

主站与导航
- 首页（中文）：<https://zh.tradingeconomics.com/>
- 指标目录：<https://tradingeconomics.com/indicators> / 中文：<https://zh.tradingeconomics.com/indicators>
- 国家目录：<https://tradingeconomics.com/countries>
- 日历：<https://tradingeconomics.com/calendar> / 国家日历：<https://tradingeconomics.com/united-states/calendar>
- 新闻流：<https://tradingeconomics.com/stream>
- 行情总览：<https://tradingeconomics.com/commodities>、<https://tradingeconomics.com/stocks>、<https://tradingeconomics.com/currencies>、<https://tradingeconomics.com/crypto>、<https://tradingeconomics.com/bonds>

页面（用于 IA 与卡片结构）
- 国家指标页：<https://zh.tradingeconomics.com/united-states/indicators>
- 指标详情页（Te 指标卡、编辑摘要、日历、新闻）：<https://zh.tradingeconomics.com/united-states/inflation-cpi>
- 指标跨国列表：<https://zh.tradingeconomics.com/country-list/inflation-rate>
- 评级列表（TE 0–100 映射表）：<https://tradingeconomics.com/country-list/rating>
- 评级历史（示例）：<https://tradingeconomics.com/ghana/rating>
- 地图视图：<https://zh.tradingeconomics.com/stocks/geomap>
- 树状图视图：<https://tradingeconomics.com/commodities/treemap>
- 预测入口：<https://tradingeconomics.com/forecasts>、<https://tradingeconomics.com/forecast/commodity>

官方文档（字段字典与限制）
- 指标快照字段（21 字段）：<https://docs.tradingeconomics.com/indicators/snapshot/>
- 日历响应字段（24 字段 + values 扩展）：<https://docs.tradingeconomics.com/economic_calendar/schema/>
- 日历 iCalendar 导出：<https://docs.tradingeconomics.com/economic_calendar/icalendar/>
- 日历文案翻译：<https://docs.tradingeconomics.com/economic_calendar/translations/>
- 行情快照字段（含市场数据免责声明原文）：<https://docs.tradingeconomics.com/markets/snapshot/>
- 指标预测字段（q1–q4 / YearEnd1–3 / ForecastLastUpdate）：<https://docs.tradingeconomics.com/forecasts/indicators/>
- API 速率与行数限制：<https://docs.tradingeconomics.com/get_started/rate-limits/>
- 文档首页：<https://docs.tradingeconomics.com/>

商业化与授权
- 会员功能页（含「20 Million Indicators for 196 countries」）：<https://tradingeconomics.com/analytics/features.aspx>
- 定价页（动态渲染，需人工复核价格）：<https://tradingeconomics.com/analytics/pricing.aspx>
- API 入口：<https://tradingeconomics.com/api/>
- 第三方复核（价格档位、试用额度、再分发限制，2026-10 更新，属二手来源）：<https://stockmarketstack.com/tools/trading-economics>

第三方引用的 TE 自述背景（二手）
- TE 评级方法论原句引用：<https://graphiconline.com/features/features/understanding-credit-rating-agencies.html>
- 评级与 TE 分数映射表（学术材料复刻）：<http://www.globeco.ro/wp-content/uploads/vol/GEO_Vol_8_No_1.pdf>

---

## 10. 未核实清单（供后续补齐）

1. `/calendar` 表格体的真实行渲染（列顺序、Tooltip、是否显示 TEForecast 列、是否有「按国家分组」视图）——需带登录态或浏览器渲染。
2. `/indicators` 与 `/countries` 的目录页内容（静态抓取仅拿到标题，主体前端渲染）。
3. 定价表精确数字与当前档位权益（站点动态渲染；仅二手来源）。
4. 指标详情页「统计数据」区所用图表库、交互（缩放/区间选择）、是否支持多指标叠加。
5. 散点/相关性视图的具体呈现与计算窗口。
6. 移动端网页的响应式断点行为（未做设备验证）。
7. 是否存在会员专属的自定义面板/自选列表/阈值告警（公开页面仅见日历桌面通知）。
8. 指标详情页「下载」锚点的具体导出格式与免费额度（需登录态）。
