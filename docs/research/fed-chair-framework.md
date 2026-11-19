# 美联储主席透镜：格林斯潘 / 伯南克 / 耶伦 / 鲍威尔的可操作分析框架

- **编写**：2026-11-18
- **查证日期**：2026-11-18（所有链接当日可访问；行情与宏观数值取自本仓库 `data/epic.db`，截至 2026-11-17/18）
- **用途**：给 EPIC 的宏观—市场研判补一层"主席反应函数"——不是复述历史，而是回答"当下这位（或这类）主席看到什么指标会转向、转向的先后顺序是什么、什么条件下这套逻辑会失效"。
- **标记约定**
  - 【原文】：一手英文原句，附中文解释；来源见第六节编号 S1…S27。
  - 【推断】：本笔记的推论，不是史料。
  - 【未核实】：仅有二手来源或未逐字核对原文。
  - 【工具】：本仓库（EPIC）能否直接算出该指标，对应 `macro_obs` 序列名或 provider。
- **体例沿用** `docs/research/dalio-framework.md`（原文/推断分离 + 编号出处）。

---

## 结论

1. **格林斯潘的一生可以压缩成一句话：央行不预测资产价格，只为资产价格破裂后的资产负债表后果买保险。** 1966 年他相信金本位是约束政府信用扩张的宪法性装置（S5）；任内他承认央行事前无法识别泡沫（S2，2002），于是把目标从"防泡沫"改成"防泡沫破裂的二次效应"（S3/S4，2004/2005 风险管理）；晚年（2008" flaw"、2014 建议中国买黄金）回到"约束"主题，但落点已从"货币纪律"变成"对法币的不信任"（S6/S7）。→ 对工具的含义：**别用估值指标预测联储转向，要用信用/流动性指标预测联储的*反应*。**
2. **四任主席的反应函数不是四个，是两类加一个共同锚。** 两类：①规则型/通胀目标制（伯南克 2012 后、耶伦、鲍威尔 2022 后）；②风险管理/相机抉择（格林斯潘、伯南克 2008–2013、鲍威尔 2020）。共同锚是**实际利率与 r\* 的缺口**：实际政策利率显著高于 r\* 且金融条件在收紧，最终必转松；显著低于 r\* 且通胀/资产价格在涨，最终必转紧。差别只在"多快、以什么名义"。
3. **可观测的转向触发器有严格排序：金融条件骤紧/融资市场失灵 ≫ 失业率上行拐点 > 通胀读数本身。** 1998 LTCM、2008、2019 回购、2020、2023 SVB 全是第一类；2001、2007–08、2024 是第二类；通胀读数几乎从不**单独**触发转向，它只决定转向的"速度上限"和"幅度上限"。这条排序是本笔记对工具最有用的输出。
4. **"格林斯潘看跌期权"不是"跌了就救"，而是"系统性重要 + 已传导至实体"才救。** 判据是"低概率 × 高损失"的乘积（S3 原话），不是跌幅。1987 救的是流动性，1998 救的是 LTCM 传染链，2001 救的是需求，2003 是抗通缩保险。反例同样重要：2000–2002 他照样把利率加到 6.5% 并让泡沫破掉。
5. **伯南克的"储蓄过剩"是理解"美股高估值 + 长端被买 + 低实际利率"的底层叙事，但他自己承认无法预判失衡何时无序调整**（S9，2005）。→ 工具里用"美元 + 长端实际利率 + 黄金"三件套监控这个失衡的再定价；当三者同向异常时，优先级高于任何单国基本面。
6. **耶伦把"充分就业"从点估计改成区间，并把菲利普斯曲线斜率当作不确定参数**（S13，2017 原话 "could be misspecified in some fundamental way"）。→ 对工具：失业率缺口（u − u\*）只在 |缺口| > 0.5pp 时才有信号价值，否则是噪声；工资、参与率同理。
7. **鲍威尔 2020 的 AIT 与 2022 的"pain"是同一框架的两端：对称的 2% 平均目标 + 不对称的容忍度。** 2022 之后"物价稳定责任无条件"（S16）成为新的制度承诺；2026 年沃什接手后这条承诺名义上保留（FOMC 声明 "The Committee will deliver price stability"，S20），但**前瞻指引被删除**——等价于把反应函数从公共品变成私有品，其市场后果是波动率溢价与期限溢价系统性上升。
8. **对本工具的直接含义**：仓库里真能算的"主席透镜"骨架只有五件——实际利率（US5Y_REAL/US10Y_REAL）、期限利差（US10Y−US2Y）、美元（DXY）、黄金（XAUUSD）、铜/金比；CPI、核心 PCE、失业率、M2、信用利差、FCI、Case-Shiller **全部不可得**，必须用代理并标注代理误差。凡是基于代理的结论，置信度不能超过"方向判断"。

---

## 一、框架拆解

### 0. 先放一把共同的尺子

四任主席的差异常被夸大。真正决定市场的是同一组问题：**央行的约束是什么、它怕什么、它什么时候必须动。**

| 维度 | 格林斯潘（1987–2006） | 伯南克（2006–2014） | 耶伦（2014–2018） | 鲍威尔（2018–2026.5） |
|---|---|---|---|---|
| 核心问题 | 信用扩张与资产价格的相互作用 | 总需求不足 + 金融摩擦（零下限） | 劳动力市场闲置与通胀的关系 | 通胀回归 + 政策空间 + 独立性 |
| 主工具 | 联邦基金利率 + 口头/流动性干预 | 利率 + 资产负债表 + 前瞻指引 | 利率 + 缓慢正常化 | 利率 + 资产负债表 + 沟通框架（AIT） |
| 资产价格 | 只看"传导"，不设目标（S1/S2） | 视为金融条件的一部分 | 视为财富效应渠道 | 明确写进"金融条件"（S20 记者会） |
| 对规则态度 | 明确反对简单规则（S3："will be inadequate"） | 支持规则但保留相机（2012 起 2% 目标） | 规则 + 判断，重视预期锚 | 2020 刻意"不绑定公式"（S15） |
| 典型转向触发器 | 系统性事件 → 流动性；通缩尾部 → 先发制人 | 失业率/通胀阈值 + 金融条件 | 劳动力市场闲置收敛 | 通胀预期失锚 → 无条件紧缩；金融条件骤紧 → 定向救助 |
| 失败模式 | 长期低利率 + 不刺破泡沫 → 2008 | 前瞻指引被当承诺 → 2013 taper tantrum | 低估通胀（"transitory" 归属鲍威尔时代，但框架同源） | 2021"transitory" 误判；2022 急转的沟通成本 |

> 【推断】这张表的用法不是给主席贴标签，而是**给当前主席找最近的类比**：沃什 2026 的组合（删前瞻指引 + 高实际利率 + 财政主导 + 强美元偏好）在历史上最接近 **1994–1995 的格林斯潘 + 1979–1982 的沃尔克**，而不是 2018 的鲍威尔。

---

### 1. 格林斯潘：从"金本位约束"到"风险管理"，再到"对法币的不信任"

#### 1.1 货币哲学的三段演变

**第一段（1966）：金本位 = 约束政府信用扩张的宪法性装置。**

【原文】"An almost hysterical antagonism toward the gold standard is one issue which unites statists of all persuasions. They seem to sense … that gold and economic freedom are inseparable, that the gold standard is an instrument of laissez-faire and that each implies and requires the other."（S5）
→ 【译】对金本位的近乎歇斯底里的敌意，是把各种国家主义者联合起来的一个议题；他们似乎感觉到，黄金与经济自由不可分割，金本位是自由放任的工具，两者互相蕴含、互相要求。

他的推理链非常清晰，而且**是可计算的**：
1. 信用工具最终都是对**有形资产**的索取权；
2. 政府债券没有有形资产背书，只有"未来税收的承诺"（【原文】"government bonds are not backed by tangible wealth, only by the government's promise to pay out of future tax revenues"，S5）；
3. 因此脱离金本位后，银行体系可以成为"无限信用扩张"的工具（【原文】"made it possible for the welfare statists to use the banking system as a means to an unlimited expansion of credit"，S5）；
4. 结论：法币体系下储蓄无法免于被通胀没收（【原文】"there is no way to protect savings from confiscation through inflation. There is no safe store of value"，S5），赤字支出"就是一种没收财富的方案"（【原文】"Deficit spending is simply a scheme for the confiscation of wealth"，S5）。

**第二段（任内 1987–2006）：承认"央行无法预知泡沫"，改用风险管理。**

1996 年那篇让他出名的演讲，重点其实不是"非理性繁荣"四个字，而是紧接着的自我怀疑：
【原文】"But how do we know when irrational exuberance has unduly escalated asset values, which then become subject to unexpected and prolonged contractions as they have in Japan over the past decade? And how do we factor that assessment into monetary policy?"（S1）
→ 【译】但我们怎么知道非理性繁荣何时把资产价值推高到过头，随后又像日本过去十年那样遭遇意外而漫长的收缩？我们又该如何把这种判断纳入货币政策？

到 2002 年他给出了答案：**根本做不到事前识别**。
【原文】"it was very difficult to definitively identify a bubble until after the fact--that is, when its bursting confirmed its existence."（S2）
→ 【译】在事实发生之前，几乎不可能确凿地识别泡沫——也就是说，要等它破裂才确认它存在过。

于是政策目标被重新定义：不刺破泡沫，只处理破裂后的债务清算与需求坍塌。
【原文】"nothing short of a sharp increase in short-term rates that engenders a significant economic retrenchment is sufficient to check a nascent bubble. The notion that a well-timed incremental tightening could have been calibrated to prevent the late 1990s bubble is almost surely an illusion."（S2）
→ 【译】除非短期利率大幅上升并造成显著的经济收缩，否则不足以遏制一个初生的泡沫；认为"时机恰当的渐进紧缩"可以精确地阻止 1990 年代末的泡沫，几乎肯定是幻觉。

**第三段（晚年 2008–2014）：回到"约束"，但落点变成对法币的不信任。**

2008 年 10 月 23 日众议院听证，他承认自己世界观有漏洞：
【原文】"I found a flaw, I don't know how significant or permanent it is, but I've been very distressed by that fact."（S6）
→ 【译】我发现了一个缺陷，我不知道它有多重要、会不会持久，但我为此非常不安。
（Waxman 追问："Do you feel that your ideology pushed you to make decisions that you wish you had not made?"——【未核实】为二手转录。）

2014 年他在 Foreign Affairs 的《Golden Rule》里建议中国把外储的一部分换成黄金，人民币可能"take on unexpected strength"，并承认"It would be a gamble"（下行风险有限，损失只是利息与储藏成本）（S7）。同年 CFR 访谈里那句被广泛引用的话：
【原文】"Gold is a currency. It is still, by all evidence, the premier currency. No fiat currency, including the dollar, can match it."（S8，【未核实】：CFR 未发布文字稿，仅二手转述）
→ 【译】黄金是一种货币。按所有证据看，它仍是首要货币；没有任何法币——包括美元——比得上它。

**核心信条（可操作版）**

| 信条 | 一手依据 | 稳定性 | 对市场的含义 |
|---|---|---|---|
| 金本位 = 约束政府信用扩张 | S5 | 1966 年极强，任内未主张恢复，晚年回潮 | 长期看，"财政赤字货币化"是黄金的结构性多头逻辑 |
| 央行无法预知泡沫 | S2 | 一生未变 | 不要用估值等联储转向；估值只影响"破裂后多痛" |
| 风险管理式决策（概率×损失） | S3 | 一生未变 | 联储对"尾部风险"的反应远快于对"中枢变化"的反应 |
| 生产率/技术乐观主义 | S1/S4 | 一生未变 | 他倾向把高增长归因于生产率而非需求过热 → 更少加息 |
| 反对简单规则 | S3 | 一生未变 | 任何"泰勒规则预测联储"的模型都会系统性失灵 |

> **注意一个常见误读**：格林斯潘从未在任内或晚年主张"恢复金本位"。他的原话结构是"金本位在历史上提供了约束"（1966）+ "黄金仍是最可靠的货币"（2014），而不是"我们应该回去"。【推断】把他说成金本位鼓吹者，会错判他的政策行为——他任内恰恰是信用扩张最猛烈的一任。

#### 1.2 看什么（指标清单）

| 看什么 | 具体口径 | 一手依据 |
|---|---|---|
| 资产负债表与资产价格 | 家庭/企业资产负债表、股价、房价 | S1："evaluating shifts in balance sheets generally, and in asset prices particularly, must be an integral part of the development of monetary policy." |
| 股权风险溢价 | 股息率 − 实际长期利率（他明确用过这个口径判断 1990 年代末） | S2 |
| 家庭净资产/可支配收入 | 2000 年前后他反复引用 | S4 |
| 长端利率之谜 | 2004–2006 短端加息 425bp 而 10Y 不动 | S10（"conundrum"，【未核实】原文未逐字核） |
| 货币供应量 | 他自己宣布 M1/M2 中间目标失效，改用更广的信息集 | S1 |
| 生产率 | 1990 年代后期他以此解释"高增长低通胀" | S1/S4 |

#### 1.3 怎么权衡

- **不对称的损失函数**：低概率 × 高损失的事件，其"乘积"要按严重程度加权，而不是按概率加权（S3 原话："The product of a low-probability event and a potentially severe outcome was judged a more serious threat…"）。这就是 1998 年"经济明明不错却降息"、2003 年"明明不需要却降到 1%"的全部理由。
- **明确自认 Bayesian**：风险管理是"application of Bayesian decisionmaking"（S3）——先验 + 新信息 + 损失函数，而不是单一规则。
- **资产价格只通过"最终目标"的棱镜看**："through the prism of the policy's ultimate objective"（S3），即资产价格只有影响到通胀/就业（通过财富效应、信贷条件）时才进入决策。
- **对"流动性幻觉"的警觉**：低风险溢价持续太久 → 投资者一旦转谨慎，风险溢价上升、资产价格下跌、支撑高价格的债务被清算（S4 原话："history has not dealt kindly with the aftermath of protracted periods of low risk premiums"）。这是他 2005 年就写下的、三年后应验的话。

#### 1.4 何时转向

| 情形 | 动作 | 案例 |
|---|---|---|
| 系统性金融事件（传染链） | **立即、大幅、超预期**注入流动性 | 1987-10-20 开盘前声明；1998-10-15 隔夜降息 25bp |
| 通缩尾部风险 | 先发制人降到"事后看过于宽松"的水平 | 2003-06 降至 1.00%（S3 自认） |
| 通胀上行但无危机 | 渐进、可预期、每次 25bp | 1994–1995（7 次 25bp→6.0%）；2004–2006（17 次 25bp→5.25%） |
| 资产价格过热 | **不动**，只口头警告 | 1996-12 演讲后仅 1997-03 加息一次 |

> 这张表解释了一个反直觉现象：**格林斯潘时代"救市"比"抑泡沫"果断得多**。因为救市是"高损失低概率"，抑泡沫是"高成本高不确定性"。

#### 1.5 代表性原话（速查）

| 场景 | 英文原句 | 中文解释 | 出处 |
|---|---|---|---|
| 泡沫不可知 | "very difficult to definitively identify a bubble until after the fact" | 事后才能确认泡沫 | S2 |
| 渐进紧缩无效 | "almost surely an illusion" | 想靠微调刺破泡沫是幻觉 | S2 |
| 央行的无知 | "There is, regrettably, no simple model of the American economy" | 没有简单的美国经济模型 | S1 |
| 前瞻性 | "we need to tighten or ease before the need for action is evident to the public at large" | 必须在公众看出必要性之前行动 | S1 |
| 风险乘积 | "The product of a low-probability event and a potentially severe outcome was judged a more serious threat" | 低概率×高损失=更严重威胁 | S3 |
| 危机中逆势宽松 | "the FOMC eased policy despite our perception that the economy was expanding at a satisfactory pace" | 明知经济不错仍降息（1998） | S3 |
| 低风险溢价的代价 | "history has not dealt kindly with the aftermath of protracted periods of low risk premiums" | 长期低风险溢价之后，历史从不温柔 | S4 |

#### 1.6 "格林斯潘看跌期权"的精确定义

不是"股指跌 10% 就救"，而是三个条件同时满足：
1. **系统性**：冲击通过杠杆/期限错配/共同持仓可传染（LTCM、货币基金、回购市场）；
2. **传导性**：已开始或即将传导至实体需求（信贷收缩、财富效应）；
3. **不可逆性**：若不管，损失会自我强化（债务-通缩、挤兑）。

满足则动作是**流动性/最后贷款人**，而不是"降息托市"。**失效条件**：如果冲击只影响估值（分子/分母变化）而不影响信用链条，联储不会救——1990 年、2000–2002 年、2022 年都是反例。

---

### 2. 伯南克：储蓄过剩 + 金融加速器 + 资产负债表

#### 2.1 三个支柱

**(a) 全球储蓄过剩（Global Saving Glut，2005）**：低长端利率不是美国政策的产物，是全球储蓄供给过剩的产物。
【原文】"the U.S. trade balance is the tail of the dog; for the most part, it has been passively determined by foreign and domestic incomes, asset prices, interest rates, and exchange rates"（S9）
→ 【译】美国贸易余额是狗尾巴；它大体上是被外国与国内收入、资产价格、利率和汇率被动决定的，而不是反过来。

逻辑与数字：老龄化富国 + 新兴市场由净借入（1996 年 −$880 亿）转为净贷出（2003 年 +$2,050 亿）→ 全球合意储蓄 > 合意投资 → 全球长期实际利率被压低 → 美国经常账户赤字（2004 年 $6,350 亿 ≈ 5.5% GDP）与低利率同时出现。"双赤字"假说解释不了 1996–2000（美国财政盈余期赤字仍在扩大）（S9）。
传导渠道的切换很关键：1996–2000 靠**股价**（财富效应），2000 年后靠**低实际利率 → 房价**；家庭财富/收入比 2004 年 5.4，1999 峰值 6.2，1960–2003 均值 4.8（S9）。

**(b) 金融加速器（Financial Accelerator）**：Bernanke–Gertler–Gilchrist (1996, *REStat* 78(1):1–15; 1999, *Handbook of Macroeconomics* vol.1C ch.21)（S11）。
→ 外部融资溢价与借款人净值反比：冲击 → 净值下降 → 溢价上升 → 投资/消费下降 → 净值再下降。**这解释了为什么"小冲击"能变成"大衰退"，也解释了为什么央行必须直接修资产负债表（QE）而不只是降息。**

**(c) 零下限下的资产负债表工具（2002 已写好剧本）**：
【原文】"the U.S. government has a technology, called a printing press (or, today, its electronic equivalent), that allows it to produce as many U.S. dollars as it wishes at essentially no cost."（S12）
→ 【译】美国政府有一项技术，叫印钞机（今天叫电子等价物），可以让它想印多少美元就印多少，成本基本为零。
同篇给出完整弹药清单：通胀缓冲垫（目标 1–3% 而非 0）、维护金融稳定、低通胀下"more preemptively and more aggressively"降息、承诺零利率更久、给特定期限国债收益率设上限、买 agency/MBS、贴现窗口接受私人抵押品、买外国政府债、货币化减税= Friedman 的"helicopter drop"；并以 1933–34 罗斯福对黄金贬值 40% 作为"零利率下货币政策仍有效"的例证（CPI 1932 −10.3% → 1933 −5.1% → 1934 +3.4%）（S12）。

#### 2.2 看什么

| 看什么 | 口径 | 依据 |
|---|---|---|
| 长期实际利率 | 10Y TIPS / 全球储蓄供给 | S9 |
| 期限溢价与"谜" | 短端加息而长端不动 | S9 |
| 房价/收入、财富/收入 | 传导渠道指标 | S9 |
| 信用利差与外部融资溢价 | 金融加速器的核心变量 | S11 |
| 通胀预期 | TIPS 盈亏平衡、Survey | S12/S15 |
| 经常账户与美元 | 失衡的规模与方向 | S9 |

#### 2.3 怎么权衡

- **双 mandate 但权重不对称**：2012-01-25 FOMC 首次发布 2% 长期通胀目标（S15 引用）后，通胀目标成为名义锚；就业目标用"最大就业"的区间表述。
- **零下限下"做得过多"优于"做得过少"**：2008–2013 的 QE1/2/3、OT、前瞻指引都体现这一点。
- **前瞻指引是双刃剑**：2012 年 12 月起用"失业率 6.5%、通胀 2.5%"的阈值指引，本意是压低长端，实际把政策变成了"可被市场倒计时的承诺"。

#### 2.4 何时转向

| 时间 | 动作 | 依据 |
|---|---|---|
| 2012-09 | QE3 无限量 MBS | 就业改善不足（S14：劳动力市场停滞是 "grave concern"） |
| 2012-12 | 阈值式前瞻指引 | 压低长端 |
| 2013-05-22 | 证词暗示"in the next few meetings"可能 taper | 数据改善 |
| 2013-12 | 正式 taper | 失业率降至 7.0% |
| 2015-12 | 首次加息 | 失业率 5.0%，通胀接近目标 |

#### 2.5 代表性原话

| 场景 | 英文原句 | 中文解释 | 出处 |
|---|---|---|---|
| 印钞机 | "the U.S. government has a technology, called a printing press" | 政府总能制造通胀 | S12 |
| 通缩概率 | "the chance of significant deflation in the United States in the foreseeable future is extremely small" | 通缩概率极小（但仍准备剧本） | S12 |
| 狗的尾巴 | "the U.S. trade balance is the tail of the dog" | 贸易逆差是被决定的 | S9 |
| 无序调整 | "the risk of a disorderly adjustment in financial markets always exists" | 无序调整风险常在 | S9 |
| 更多宽松 | "will provide additional policy accommodation as needed" | 需要时继续宽松（2012） | S14 |
| 就业是"严重关切" | "grave concern" | 劳动力市场停滞 | S14 |

#### 2.6 教训

**前瞻指引的阈值会被市场当成承诺，退出时产生 taper tantrum。** 2013 年 5–12 月，10Y 从约 1.6% 升至约 3.0%，而美国经济并未恶化——这是纯粹的"沟通冲击"（详见案例 5）。这条教训在 2026 年被反向使用：沃什删除前瞻指引，等于主动放弃"用沟通管理长端"的工具。

---

### 3. 耶伦：劳动力市场优先，菲利普斯曲线是不确定参数

#### 3.1 看什么

| 看什么 | 口径 | 依据 |
|---|---|---|
| 劳动力市场"闲置" | U3、U6、参与率、长期失业、离职率 | S19（2014 年"considerable slack"，【未核实】） |
| 工资增长 | 平均时薪、ECI | 同上 |
| 通胀与预期的偏离 | 核心 PCE、5y5y、Survey | S13 |
| 菲利普斯曲线斜率 | 劳动利用率对通胀的传导系数 | S13 原话："The influence of labor utilization on inflation has become quite modest over the past 20 years" |

#### 3.2 怎么权衡

耶伦 2017 年那篇 NABE 演讲是整个"后危机框架"最诚实的自白：
【原文】"My colleagues and I may have misjudged the strength of the labor market, the degree to which longer-run inflation expectations are consistent with our inflation objective, or even the fundamental forces driving inflation."（S13）
→ 【译】我和同事们可能误判了劳动力市场的强度、长期通胀预期与目标的一致程度，甚至误判了驱动通胀的基本力量。
【原文】"the conventional framework for understanding inflation dynamics could be misspecified in some fundamental way"（S13）
→ 【译】理解通胀动态的常规框架，可能在某些根本层面就是设定错误的。

她的操作含义：**当失业率低于 u\* 而通胀不起来时，不要用模型去"补"通胀，而要先怀疑模型。** 2017 年 9 月失业率 4.4%，FOMC 长期失业率中位数约 4.5%，她判断"generally healthy labor market, not one in which substantial slack remains or one that is overheated"（S13）——即已经接近充分就业，但通胀传导很弱，于是选择"渐进加息 + 缩表"，而不是加速紧缩。

#### 3.3 何时转向

| 时间 | 动作 | 触发 |
|---|---|---|
| 2015-12 | 首次加息（她投的） | 失业率 5.0%，"闲置"基本消化 |
| 2016-12 / 2017-03 / 06 / 12 | 每年 1–3 次 | 渐进正常化 |
| 2017-10 | 启动缩表 | 政策正常化的一部分 |

#### 3.4 代表性原话

| 场景 | 英文原句 | 中文解释 | 出处 |
|---|---|---|---|
| 框架可能错 | "could be misspecified in some fundamental way" | 常规通胀框架可能根本错误 | S13 |
| 可能误判 | "may have misjudged the strength of the labor market" | 可能误判劳动力市场 | S13 |
| 传导变小 | "The influence of labor utilization on inflation has become quite modest" | 劳动利用率对通胀的影响已很温和 | S13 |
| 市场健康 | "not one in which substantial slack remains or one that is overheated" | 既无显著闲置也不过热 | S13 |

> **注**：耶伦 2014 年 3 月芝加哥演讲"considerable slack"以及 2014-08-22 Jackson Hole《Labor Market Dynamics and Monetary Policy》为【未核实】——未取到原文全篇，仅据 Reuters/BI/Washington Examiner 转述；"I think this extraordinary commitment is still needed and will be for some time" 为转述引语。

---

### 4. 鲍威尔：平均通胀目标 → "疼痛" → 独立性

#### 4.1 看什么

| 看什么 | 口径 | 依据 |
|---|---|---|
| 金融条件 | 他明确把"financial conditions"当政策变量（2026 记者会 S20） | S20 |
| 劳动力市场紧度 | 失业率、职位空缺/失业人数、工资 | S15/S16 |
| 通胀预期 | 5y5y、Survey、TIPS | S15 |
| 供给冲击 | 能源、供应链、地缘 | S16/S20 |
| 财政/债务可持续性 | 利息支出、期限溢价 | 【推断】 |

#### 4.2 怎么权衡

**2020 框架（AIT）**：
【原文】"we will seek to achieve inflation that averages 2 percent over time"；"following periods when inflation has been running below 2 percent, appropriate monetary policy will likely aim to achieve inflation moderately above 2 percent for some time"；"a flexible form of average inflation targeting"（S15）
→ 【译】我们将寻求让通胀在一段时间内平均为 2%；在通胀低于 2% 的时期之后，适当的政策可能旨在让通胀在一段时间内适度高于 2%；这是一种灵活形式的平均通胀目标制。
就业目标从 "deviations" 改为 "shortfalls"：
【原文】"employment can run at or above real-time estimates of its maximum level without causing concern, unless accompanied by signs of unwanted increases in inflation or the emergence of other risks"（S15）
→ 【译】就业可以处于或高于实时估计的最大水平而不引起担忧，除非伴随不受欢迎的通胀上升或其他风险。
四个结构性驱动：潜在增速中位数 2.5%→1.8%；中性联邦基金利率中位数 4.25%→2.5%；2019 年失业率近 50 年低位而通胀未起；菲利普斯曲线平坦化（u\* 中位数 5.5%→4.1%）（S15）。

**2022 反转**：
【原文】"Restoring price stability will take some time and requires using our tools forcefully"；"there will very likely be some softening of labor market conditions … they will also bring some pain to households and businesses"；"a failure to restore price stability would mean far greater pain"（S16）
→ 【译】恢复物价稳定需要时间，需要有力使用工具；劳动力市场很可能走软，这会给家庭和企业带来痛苦；但恢复物价稳定失败将意味着远得多的痛苦。
【原文】"the current high inflation in the United States is the product of strong demand and constrained supply, and … the Fed's tools work principally on aggregate demand"（S16）
→ 【译】当前美国的高通胀是强需求与受限供给的产物，而联储的工具主要作用于总需求。——这句话的潜台词是：联储知道自己只能压需求，压不了供给，所以必须压到需求足够弱。

#### 4.3 何时转向

| 时间 | 动作 | 触发 |
|---|---|---|
| 2022-03 | 首次加息 25bp | CPI 7.9%，失业率 3.6% |
| 2022-06/07/09/11 | 连续 75bp×4 | CPI 破 9% |
| 2023-03 | SVB 后仍加 25bp，另设 BTFP | 分离"金融稳定"与"货币紧缩" |
| 2023-07 | 最后一次加息至 5.25–5.50% | 通胀回落 |
| 2024-09 | 一次降 50bp | 失业率上行、通胀接近 2% |
| 2024-12 后 | 暂停/缓慢 | 通胀黏性 |
| 2026 | 交棒沃什，政策转为边际收紧 | 通胀 "remains elevated" |

#### 4.4 代表性原话

| 场景 | 英文原句 | 中文解释 | 出处 |
|---|---|---|---|
| 平均目标 | "we will seek to achieve inflation that averages 2 percent over time" | 一段时间内平均 2% | S15 |
| 就业短缺口 | "shortfalls of employment from its maximum level" | 只看"不足"，不看"超出" | S15 |
| 疼痛 | "they will also bring some pain to households and businesses" | 紧缩必有痛苦 | S16 |
| 坚持到底 | "we must keep at it until the job is done" | 不达目的不罢休 | S16 |
| 责任无条件 | "Our responsibility to deliver price stability is unconditional" | 物价稳定责任无条件 | S16 |
| 不是 QE | "This is not QE." | 2019 年扩表是储备管理（S17） | S17 |

#### 4.5 独立性

2018–2019 年与白宫的公开冲突、2025–2026 年对理事会的政治压力，使"独立性"本身成为一个可交易的变量。【推断】对市场而言，独立性受质疑的定价方式是：**长端期限溢价上移 + 黄金与实际利率的负相关减弱 + 美元风险溢价上升**。2026 年的数据支持前两条（见第五节）。

---

## 二、可计算化：指标、口径与工具内可得性

### 2.1 指标表（26 项）

> "方向"列指该指标**上行**时对"风险资产（美股/信用）"的通常含义；"双向"表示取决于驱动因素（增长 vs 通胀）。可计算性按本仓库 `data/epic.db` 的 `macro_obs`/`market` 实际覆盖判断，最新值截至 2026-11-17/18。

| # | 指标 | 定义 / 计算 | 含义（主席透镜） | 数据源 | 本工具可得性 | 方向 |
|---|---|---|---|---|---|---|
| 1 | 实际政策利率 | EFFR − 10Y 盈亏平衡（或 EFFR − 核心通胀代理） | 政策松紧的第一近似 | NY Fed（EFFR）+ Treasury（BE） | ✅ 可算：`EFFR`、`US10Y_BE` | 上行 → 风险资产承压 |
| 2 | 实际政策利率缺口 | 上式 − r\*（r\* 取 0.5–1.0% 区间假设） | 是否"实质紧缩" | 需 r\*，本工具无 | ⚠️ 需外部假设（标注） | 缺口 > 0 → 紧缩 |
| 3 | 5Y 实际利率 | `US5Y_REAL` | 中期实际融资成本 | home.treasury.gov | ✅ 可算（2022-01 起） | 上行 → 估值压缩 |
| 4 | 10Y 实际利率 | `US10Y_REAL` | 全球资产定价锚 | 同上 | ✅ 可算 | 上行 → 股/金承压 |
| 5 | 期限利差 10Y−2Y | `US10Y` − `US2Y` | 周期与衰退信号 | Treasury | ✅ 可算 | 倒挂 → 衰退概率↑（但有时滞） |
| 6 | 期限利差 30Y−10Y | `US30Y` − `US10Y` | 期限溢价 / 财政风险 | Treasury | ✅ 可算 | 陡峭化 → 财政主导风险 |
| 7 | 10Y 盈亏平衡通胀 | `US10Y_BE` | 市场通胀预期 | Treasury（nominal−real） | ✅ 可算 | 上行 → 紧缩预期 |
| 8 | 5Y5Y 远期通胀代理 | 2×`US5Y_BE` − `US10Y_BE`（粗代理，非严格远期） | 长期锚 | 计算 | ⚠️ 近似，误差大 | 上行 → 失锚风险 |
| 9 | 2Y 名义收益率 | `US2Y` | 市场对 2 年政策路径定价 | Treasury | ✅ 可算 | 上行 → 紧缩预期 |
| 10 | 政策预期差 | `US2Y` − `EFFR`（12 个月视角） | 市场是否在定价转向 | 计算 | ✅ 可算 | > 0 → 市场定价加息 |
| 11 | 金融条件代理 FCI | z(SPX 20d 收益) + z(DXY 20d) + z(10Y_REAL 20d 变化) + z(SOFR−EFFR) | 联储"看什么"的合成 | 计算 | ✅ 可构造（需标定权重） | 骤紧 → 联储转鸽概率↑ |
| 12 | 融资压力利差 | `SOFR` − `EFFR`（日） | 回购市场紧张度 | NY Fed | ✅ 可算 | > 15bp 持续 → 流动性事件 |
| 13 | 信用脉冲 / 财政脉冲代理 | `US_MTS_DEFICIT` 12 个月滚动 / 名义 GDP | 信用扩张方向 | Treasury MTS + WB | ⚠️ 月度/年度混合，样本短（2025-04 起） | 扩张 → 需求支撑 |
| 14 | M2 同比 | — | 传统货币数量指标 | 无直连 | ❌ 不可得；代理：`US_FED_DEBT` 同比 + 银行信贷（无） | — |
| 15 | 失业率缺口 u − u\* | — | 劳动力市场松紧 | BLS 不可得 | ❌；仅年度 `WB_US_UNEMPLOYMENT`（至 2025）+ 财经日历事件名 | 缺口转正 → 衰退 |
| 16 | 核心 PCE 同比 | — | 联储最看重的通胀 | BEA 不可得 | ❌；代理：`US10Y_BE` + 铜金比 + 油价 | — |
| 17 | 股市/GDP（Buffett 指标代理） | `SPX`（或市值代理） / 名义 GDP（年化插值） | 资产价格相对实体规模 | 行情 + WB 年度 GDP | ⚠️ 可算但年度分母需插值 | 极高 → 格林斯潘式警告概率↑（非卖出信号） |
| 18 | 房价/收入 | — | 2008 式传导渠道 | Case-Shiller 无 | ❌ 不可得（用 SPX/租金代理亦不可得） | — |
| 19 | 私人部门信贷/GDP | — | 信用深度与杠杆 | BIS 无（IMF/WB 年度可近似） | ❌ 仅年度 IMF WEO / WB | 上升 → 脆弱性积累 |
| 20 | 美元指数 DXY | 6 货币篮子 | 全球美元流动性 | 自建（`symbols.py`） | ✅ 可算（日） | 上行 → 全球紧缩 |
| 21 | 黄金（实际金价） | `XAUUSD` / CPI 代理 | 法币信用对冲 | 行情 + 年度 CPI | ✅ 可算（分母粗） | 上行 → 避险/去美元化 |
| 22 | 铜金比 | `HG` / `XAUUSD`（建议各自标准化后再比，规避单位问题） | 增长 vs 避险 | 行情 | ✅ 可算（单位需核对，建议用 z-score） | 上行 → 再通胀 |
| 23 | 美股回撤 | `SPX` / 52 周高点 − 1 | 风险状态 | 行情 | ✅ 可算 | < −15% → 金融条件骤紧 |
| 24 | 中美利差 | `CN10Y` − `US10Y` | 汇率与政策空间约束 | 两库 | ✅ 可算 | 负值扩大 → 人民币压力 |
| 25 | 美元/人民币 | `USDCNH` | 外部约束 | 行情 | ✅ 可算 | 上行 → 中国宽松受限 |
| 26 | 财政利息负担 | `US_MTS_INTEREST` / `US_MTS_RECEIPTS` | 财政主导风险 | Treasury MTS | ✅ 可算（月度，2025-04 起） | > 25% → 财政主导 |

### 2.2 组合状态机（把指标压成 5 个 regime）

| regime | 触发条件（可计算） | 主席行为预期 | 资产方向 |
|---|---|---|---|
| **A. 金发女孩** | 10Y_REAL 1.0–2.0%，2s10s > 0，FCI 宽松，SPX 接近高点 | 维持，口头紧缩 | 股 > 债 > 金 |
| **B. 过热/紧缩中** | EFFR − BE > 1.5%，2s10s 走平/倒挂，DXY 上行 | 继续加息或维持高位 | 现金 > 商品 > 股 |
| **C. 滞胀** | BE > 2.5%，SPX 回撤 > 10%，铜金比下行 | 两难，优先通胀 | 商品/金 > 现金 > 股债 |
| **D. 衰退/宽松** | 2s10s 倒挂后转陡，SPX 回撤 > 15%，SOFR−EFFR 上行 | 快速降息 | 债 > 股 > 商品 |
| **E. 流动性危机** | SOFR−EFFR > 15bp 持续 3 日，或 SPX 单日 < −5%，DXY 急升 | 立即流动性工具 | 现金/美元 > 金 > 股 |

> 【推断】这个状态机的价值不在预测，而在**给当前市场贴一个标签，再检查该标签下"主席应该做什么"与"市场在定价什么"是否背离**。背离就是交易机会。

### 2.3 计算清单（给实现者的最小集）

```
# 已可直接算（macro_obs）
real_policy   = EFFR - US10Y_BE
real5, real10 = US5Y_REAL, US10Y_REAL
term_2s10s    = US10Y - US2Y
term_30s10s   = US30Y - US10Y
be10, be5     = US10Y_BE, US5Y_BE
fwd5y5y_proxy = 2*US5Y_BE - US10Y_BE
funding_stress= SOFR - EFFR
debt_yoy      = pct_change(US_FED_DEBT, 252)
interest_ratio= US_MTS_INTEREST / US_MTS_RECEIPTS
# 行情（market 表）
fci_proxy     = z(spx_ret20d) + z(dxy_chg20d) + z(d_real10_20d) + z(funding_stress)
cu_au         = z(HG) - z(XAUUSD)     # 单位不同，先各自 z-score
drawdown      = SPX/rolling_max(SPX,252) - 1
cn_us_spread  = CN10Y - US10Y
```

**必须标注的不确定性**：r\*（0.5–1.0% 为假设）、CPI/PCE（不可得）、失业率（仅年度）、M2（不可得）、信用利差（不可得）、房价（不可得）。凡结论依赖这些变量的，降级为"方向判断"。

### 2.4 指标与"主席透镜"的对应关系

| 主席 | 最该看的 3 个可得指标 | 最缺的 3 个指标 |
|---|---|---|
| 格林斯潘 | 10Y_REAL、SPX 回撤、家庭财富代理（SPX/GDP） | 房价/收入、信用利差、家庭资产负债表 |
| 伯南克 | 10Y_REAL、BE、SOFR−EFFR | 信用利差（OAS）、MBS 利差、银行准备金 |
| 耶伦 | 失业率（缺）、BE、工资（缺） | 核心 PCE、U6、参与率 |
| 鲍威尔 | FCI 代理、BE、2s10s | 核心 PCE、职位空缺、通胀预期调查 |

---

## 三、可证伪规则 R1–R15

> 每条格式：**if 条件 → then 方向/状态；失效条件**。规则都可以用 2.3 的变量集计算；标注 ✅ 的是本工具当日可直接判定的。

**R1（实际利率—风险资产）** ✅
if `US10Y_REAL` 20 日变化 > +30bp 且 `term_2s10s` < 0 → then 美股/信用承压，成长股相对价值股跑输；黄金承压。
失效条件：实际利率上行由**生产率/增长预期**驱动（此时 EPS 上修抵消贴现率），或外资/央行结构性买盘压低期限溢价（2014–2016、2020–2021 反例）。

**R2（金融条件骤紧 → 联储转鸽 → 黄金受益）** ✅
if `fci_proxy` 20 日 z 值 < −1.5（骤紧）且 `EFFR − US10Y_BE` > 1.0% → then 未来 3 个月内联储转鸽概率显著上升；黄金与实际利率的负相关增强。
失效条件：通胀预期同步失锚（BE 与金价同涨、实际利率不再主导）；或联储选择"定向工具"而非降息（2023 SVB）。

**R3（融资压力）** ✅
if `SOFR − EFFR` > 15bp 持续 3 个交易日 → then 流动性事件概率上升，联储将扩表/降息；短端利率下行，曲线陡峭化。
失效条件：季末/年末的常规窗口效应（通常 1–3 日回落）；或准备金充裕、只是技术性错配（2019-09 的初判）。

**R4（曲线倒挂 → 衰退，但有长时滞）** ✅
if `US10Y − US2Y` < 0 持续 ≥ 3 个月 → then 12–24 个月内衰退概率显著上升；首次降息往往发生在衰退确认前后。
失效条件：倒挂由**期限溢价**（QE/外储买盘）而非政策预期驱动（2019、2022–2024 的争论）；软着陆（1995、2019、2024）。

**R5（实际利率 → 黄金）** ✅
if `US10Y_REAL` > 2.5% 且 DXY 上行 → then 黄金承压；金价与实际利率负相关增强。
失效条件：央行购金/去美元化主导（2022 后多次出现金价与实际利率同涨）；地缘冲突溢价。**2026 年当前状态即为此规则的强验证：US10Y_REAL 2.89%，XAUUSD 自 1 月高点 −30.4%。**

**R6（估值极端 ≠ 卖出）** ⚠️
if `SPX/GDP` 处于历史 95 分位以上且 `fci_proxy` 宽松 → then 格林斯潘式"非理性繁荣"警告出现的概率上升；但**不构成做空信号**，历史上警告后市场仍可上涨 1–3 年（1996–2000）。
失效条件：信用利差同步走阔（不可得，需外部数据）——那才是"泡沫 + 脆弱"的组合。

**R7（通胀读数单独不触发转向）** ✅
if 核心通胀代理上行但 `fci_proxy` 未紧、失业率未上行 → then 联储大概率"口头鹰派、行动迟缓"。
失效条件：通胀预期失锚（BE > 2.5% 且 5y5y 上行），此时联储会无条件紧缩（2022 反例）。

**R8（美元—实际利率共振 → 全球紧缩）** ✅
if DXY 20 日上行 > 2% 且 `US10Y_REAL` 同向 → then 新兴市场/人民币承压，中国央行宽松空间受限（`CN10Y − US10Y` 为负且扩大）。
失效条件：美元上行由**避险**驱动（此时美债也涨，实际利率下行），或中国资本管制/结汇政策对冲。

**R9（铜金比 = 增长/避险切换）** ✅
if `cu_au`（z 差）连续 10 日上行且 `US10Y_BE` 上行 → then 再通胀交易：周期股/大宗 > 黄金/长久期债。
失效条件：铜价上行由**供给扰动**（罢工、制裁）而非需求驱动。

**R10（黄金/美股比 → 风险 regime）** ✅
if `XAUUSD/SPX` 突破 12 个月新高 → then 避险 regime 确认（C 或 E），降低风险敞口。
失效条件：黄金单独因央行购金上涨而美股平稳（2024–2025 部分时段）。

**R11（删除前瞻指引 → 波动率与期限溢价上升）** ⚠️【推断，历史样本少】
if 联储声明连续 2 次会议不含前瞻指引措辞 → then 利率波动率（MOVE 代理）与期限溢价上升，股指估值压缩；"意外转向"的频率上升。
失效条件：市场已通过其他渠道（点阵图、记者会）获得同等信息；或财政/外储买盘压制期限溢价。

**R12（长端上行的性质决定股债反应）** ✅
if 10Y 上行且 `US10Y_BE` 同步上行（真实利率驱动）→ then 估值杀，股债双杀；if 10Y 上行而 BE 下行（期限溢价/财政驱动）→ then 股债双杀更剧烈，黄金相对占优。
失效条件：上行幅度 < 30bp（噪声）。

**R13（中美利差 → 人民币与政策空间）** ✅
if `CN10Y − US10Y` < −250bp 且扩大 → then 人民币贬值压力，中国降息受约束，A 股外资流出压力。
失效条件：中国采取逆周期因子/资本管制；或美国利率快速下行。

**R14（财政主导）** ✅
if `US_MTS_INTEREST / US_MTS_RECEIPTS` > 25% 且 `EFFR` 高于名义 GDP 增速 → then 财政主导风险上升：长端 bear steepening，黄金结构性受益，联储独立性溢价上升。
失效条件：名义增长 > 利率（债务/GDP 自然下降）；或财政整顿。

**R15（主席更替/独立性受质疑）** ⚠️
if 主席更替或独立性受公开质疑 → then 黄金与实际利率的负相关**减弱**（去美元化溢价），长端期限溢价上行，美元风险溢价上升。
失效条件：新主席迅速建立信誉（如 1979 沃尔克、2026 沃什若成功压通胀）。

---

## 四、案例（8 个）

> 表中历史价格与利率为公开常识性数值，标"约"；**精确日频数据本仓库行情库仅覆盖 2022 年后**，2022 年前数值来自公开资料，未逐条复核原始数据源。

| # | 时间 | 当时指标状态 | 主席判断 | 市场反应 | 可复用规律 | 出处 |
|---|---|---|---|---|---|---|
| 1 | 1996-12 非理性繁荣 | S&P P/E 约 20（1995 约 15，2000 约 30）；10Y 约 6.3%；失业率约 5.4% | 只提出疑问，明确说"不知道如何纳入政策"；1997-03 才加息 25bp | 演讲后全球股市短暂下跌（日经次日跌约 3%，【未核实】），但 S&P 此后 3 年多涨约 1 倍 | 口头警告 ≠ 政策；"警告后继续涨"是常态 | S1/S2 |
| 2 | 1998 LTCM | S&P 7–10 月约 −19%；信用利差飙升；10Y 跌至约 4.2%；EFFR 5.50% | "the FOMC eased policy despite our perception that the economy was expanding at a satisfactory pace"；9/29、10/15（隔夜）、11/17 三次降息 25bp | V 型反转，1998Q4 S&P 约 +21% | 系统性传染 → 立即流动性；判据是"传导"，不是跌幅 | S3 |
| 3 | 2003–2006 低利率与房地产 | EFFR 1.00%（2003-06）→ 5.25%（2006-06，17 次 25bp）；10Y 4.0–4.6%（conundrum）；房价指数 2000–2006 约 +90%；财富/收入 5.4 | 2003 年降息是"抗通缩保险"（自认事后看过于宽松）；拒绝用加息刺破房价（2002 逻辑）；渐进加息 | 房价 2006 见顶，2007–08 次贷危机；股市 2007 见顶 | 渐进紧缩无法约束资产泡沫；事后补救成本 >> 事前 | S2/S3/S9/S10 |
| 4 | 2008 QE | EFFR 5.25%→0–0.25%（2007-09→2008-12）；10Y 低至约 2.1%；TED 利差约 4.5pp（2008-10）；S&P 峰谷约 −57% | 2002 年剧本已写好："printing press"；QE1 约 1.75 万亿美元，2008-11 宣布购买 MBS/agency | 2009-03 见底；此后十年长端低位 | 零下限下"资产负债表"是主工具；剧本可提前 6 年写好 | S12 |
| 5 | 2013 taper tantrum | 10Y 约 1.6%（2013-05）→ 约 3.0%（2013-12）；失业率约 7.5%；核心 PCE 约 1.1% | 2013-05-22 证词称可能"in the next few meetings"缩减；2013-12 才真正 taper | 10Y 上行约 140bp；新兴市场货币大跌（印度卢比等）；美股 2013 全年仍约 +30% | 沟通冲击 > 政策冲击；前瞻指引退出会产生"预期利率跳升" | S18/S19 |
| 6 | 2019 回购市场 | 2019-09-17 SOFR 盘中约 5.25% vs EFFR 2.13%；准备金短缺；EFFR 已从 2.50% 降至 1.75%（三次降息） | "This is not QE."；10 月起每月约 600 亿美元短债购买（储备管理） | 回购利率回落；S&P 2019 约 +29% | 技术性流动性紧张可迫使联储扩表；"QE"的边界被重新定义 | S17 |
| 7 | 2020 疫情 | S&P 23 个交易日约 −34%；10Y 低至约 0.31%（2020-03-09）；VIX 约 82；EFFR 1.58%→0.08% | 3 月两次紧急降息共 150bp + 无限 QE + 约 2.3 万亿美元信贷工具 | 2020-03-23 见底；纳指当年约 +43% | 流动性危机中"规模"比"价格"重要；央行资产负债表 = 风险资产底 | S15（框架）/公开史实 |
| 8 | 2022–23 加息 + SVB | EFFR 0.08%→5.33%（2022-03→2023-07，16 个月约 +525bp）；CPI 峰值 9.1%（2022-06）；10Y 峰值约 4.98%（2023-10）；2s10s 自 2022-07 倒挂 | 2022-08 "pain"；2023-03 SVB 后设 BTFP，但仍加息 25bp | 2022 S&P 约 −19%（盘中约 −25%）；2023 银行股崩、纳指约 +43%（AI） | 曲线倒挂 + 快速加息 → 金融体系脆弱点暴露；用"定向工具"分离金融稳定与货币紧缩 | S16 + 本仓库 EFFR 序列 |

**从 8 个案例里能提炼的三条元规律**：
1. **联储的"救"总在"泡沫破"之后，且救的是信用链不是估值**（案例 2/4/7/8）。
2. **联储的"紧"总比通胀数据慢半拍，且一旦开始就倾向过度**（案例 3/8）——因为要建立信誉。
3. **沟通本身的冲击可以等于甚至大于政策冲击**（案例 1/5，以及 2026 删除前瞻指引）。

---

## 五、当下（2025–2026）研判：事实与推断分开

### 5.1 有出处的事实

**政策路径（本仓库 `EFFR` 序列，日频）**
- 2024-09 起降息，EFFR 从 5.33%（2024-08）降至 3.73%（2025-12），累计约 −175bp。
- 2026-01 至 2026-08 稳定在约 3.62–3.64%；2026-09 回升至 3.749%；2026-10/11 为 3.88%。
- 2026-10 FOMC 维持目标区间 3.75%–4.00%，Hammack、Cook 两张反对票均主张加息 25bp（S20/S21，二手）。
- 2026-06 声明为 2007 年以来最短，删除前瞻指引；10 月声明称活动"strong pace"、通胀"remains elevated"、"The Committee will deliver price stability"（S20/S21/S23）。
- Warsh 2026-05-22 宣誓就职（新华社）；宣布沟通等任务组；2027 年起每年一次会议只谈策略不投票，2028 年为两次策略 + 六次政策会议（S21）。

**市场与财政（本仓库行情/宏观序列，2026-11-17/18）**
- 10Y 名义 5.10%，10Y 实际 2.89%，5Y 实际 2.64%，10Y 盈亏平衡 2.21%；2Y 4.80%，30Y 5.46% → 2s10s 约 +30bp（已转正、偏陡），30s10s 约 +36bp。
- DXY 103.66；USDCNH 6.667；XAUUSD 3,769.6（自 2026-01-28 高点 5,414.84 下跌约 30.4%）。
- SPX 7,340.53（自 2026-10-06 高点 7,818.93 回撤约 6.1%）；NDX 27,001.78；DJIA 50,759.42。
- 美国联邦债务 40.66 万亿美元；2026-10 MTS：利息 1,030.8 亿美元、赤字 4,040.6 亿美元、支出 7,730.0 亿美元、收入 3,689.4 亿美元 → 利息/收入约 27.9%。
- 中国：CN10Y 1.5892%，CN2Y 1.2301%，CN10Y−US10Y 约 −351bp；沪深 300 3,983.77。

### 5.2 【推断】这些数字意味着什么

1. **实际利率处于 2008 年以来最紧的状态。** EFFR − 10Y_BE ≈ 3.88 − 2.21 = 1.67%，10Y 实际收益率 2.89% 远高于 2010 年代 0–1% 的常态。若 r\* 在 0.5–1.0%（HLW 口径，本工具不可得），政策利率比中性高约 0.7–1.2pp。**这更像 1994–1995 或 2006 的组合，而不是 2019。**
2. **黄金 −30% 与实际利率 2.89% 是对 R5 的强验证**，也说明"央行购金/去美元化"叙事目前不足以对抗实际利率。但只要 R14（利息/收入 > 25%）持续，黄金的结构性买盘不会消失——**短期由实际利率定价，长期由财政定价**。
3. **曲线已从倒挂转为正陡（2s10s +30bp、30s10s +36bp）**，同时长端名义 5% 以上。这不是"衰退已过"的典型信号，而更像"期限溢价回归 + 财政供给压力"：熊陡。若为熊陡，股权估值承压（R12）。
4. **沃什的"modest medicine"+"I'm unwilling or unable to call them tight"是刻意的反应函数模糊化**（S20）。后果：市场无法用前瞻指引给利率路径定价 → 期限溢价与利率波动率上升（R11），"意外转向"的概率上升。对工具的含义是：**不要用"点阵图/声明措辞"做预测，改用 2Y 与 EFFR 的差（R10 指标）反推市场定价，再看它是否与数据背离。**
5. **两张"主张加息"的反对票 + 通胀 "remains elevated" + 能源价格再度上行**表明：2026 年联储的内部风险偏好偏向"宁可紧过头"。若 2027 年增长走弱，沃什将面临"通胀未达标 + 就业转弱"的两难——但他的沟通框架已主动放弃了"提前铺垫"的能力，因此**转向大概率以市场意外的方式发生**（利率急降、黄金急涨、美元急跌），而不是以声明措辞渐进变化的方式发生。
6. **独立性溢价**：期货/长端/黄金的组合定价显示市场在给"政治干预联储"一个正的溢价，但目前该溢价被实际利率压制。【推断】一旦 2027 年出现"财政主导 + 降息压力"的组合，这个溢价会一次性释放。

### 5.3 预警触发条件（可每日计算，给出阈值）

| 编号 | 触发条件（工具内可算） | 含义 | 当前状态（2026-11-18） |
|---|---|---|---|
| W1 | `EFFR − US10Y_REAL` < 0 | 实际政策利率为负 → 危机式宽松模式 | 3.88 − 2.89 = +0.99，未触发 |
| W2 | `SOFR − EFFR` > 15bp 持续 3 日 | 融资市场失灵 → 联储扩表/降息 | 当前 0.05，未触发 |
| W3 | SPX 自 52 周高点回撤 > 15% 且 DXY 上行 | 全球美元紧缩 → 风险资产系统性承压 | 回撤 6.1%，未触发 |
| W4 | `US10Y_BE` < 1.8% | 通胀预期失锚向下 → 联储降息压力 | 2.21%，未触发 |
| W5 | `US_MTS_INTEREST / US_MTS_RECEIPTS` > 30% | 财政主导 → 长端 bear steepening、黄金受益 | 27.9%，接近 |
| W6 | `CN10Y − US10Y` < −400bp | 人民币压力极端 → 中国政策受限 | −351bp，接近 |
| W7 | 2s10s 转为 < −50bp（重新倒挂） | 市场重新定价衰退 | +30bp，未触发 |
| W8 | 30s10s > 60bp 且 10Y_REAL 上行 | 财政风险溢价主导 → 股债双杀 | +36bp，未触发 |

> 用法建议：把 W1–W8 做成每日检查清单，任一条触发即把"主席透镜"的权重从"看通胀"切到"看金融稳定"——这正是四任主席共同的行为模式（结论 3）。

---

## 六、出处（编号 / 链接 / 查证日期 2026-11-18）

**一手（federalreserve.gov 与官方出版物）**

- **S1** Greenspan, "The Challenge of Central Banking in a Democratic Society"（AEI Francis Boyer Lecture, 1996-12-05）— https://www.federalreserve.gov/boarddocs/speeches/1996/19961205.htm （查证 2026-11-18）
- **S2** Greenspan, "Economic volatility"（Jackson Hole, 2002-08-30）— https://www.federalreserve.gov/boarddocs/speeches/2002/20020830/ （查证 2026-11-18）
- **S3** Greenspan, "Risk and Uncertainty in Monetary Policy"（AEA, 2004-01-03）— https://www.federalreserve.gov/boarddocs/speeches/2004/20040103/default.htm （查证 2026-11-18）
- **S4** Greenspan, "Reflections on central banking"（Jackson Hole, 2005-08-26）— https://www.federalreserve.gov/boarddocs/speeches/2005/20050826/default.htm （查证 2026-11-18）
- **S5** Greenspan, "Gold and Economic Freedom"（*The Objectivist Newsletter*, 1966；收于 Ayn Rand 编 *Capitalism: The Unknown Ideal*, 1967；无官方在线原文，据转载核对）— https://www.cobdencentre.org/2010/12/alan-greenspan-gold-and-economic-freedom/ ；https://www.valueinvestingworld.com/2010/05/alan-greenspan-article-from-1966-gold.html ；PDF: https://www.usagold.com/publications/greenspan.pdf （查证 2026-11-18）
- **S7** Greenspan, "Golden Rule", *Foreign Affairs*, 2014-09-29（摘自 *The Map and the Territory* 平装版）— https://www.foreignaffairs.com/articles/united-states/2014-09-29/golden-rule （查证 2026-11-18）
- **S9** Bernanke, "The Global Saving Glut and the U.S. Current Account Deficit"（Sandridge Lecture, 2005-03-10）— https://www.federalreserve.gov/boarddocs/speeches/2005/200503102/default.htm （查证 2026-11-18）
- **S11** Bernanke, Gertler & Gilchrist (1996), "The Financial Accelerator and the Flight to Quality", *Review of Economics and Statistics* 78(1): 1–15；(1999), "The financial accelerator in a quantitative business cycle framework", *Handbook of Macroeconomics* vol.1C ch.21（书目核对，未取原文）
- **S12** Bernanke, "Deflation: Making Sure 'It' Doesn't Happen Here"（2002-11-21）— https://www.federalreserve.gov/boarddocs/speeches/2002/20021121/default.htm （查证 2026-11-18）
- **S13** Yellen, "Inflation, Uncertainty, and Monetary Policy"（NABE, 2017-09-26）— https://www.federalreserve.gov/newsevents/speech/yellen20170926a.htm （查证 2026-11-18；BIS 镜像 https://www.bis.org/speeches/20171012-inflation-uncertainty-and-monetary-policy ）
- **S15** Powell, "New Economic Challenges and the Fed's Monetary Policy Review"（Jackson Hole, 2020-08-27）— https://www.federalreserve.gov/newsevents/speech/powell20200827a.htm （查证 2026-11-18）
- **S16** Powell, "Monetary Policy and Price Stability"（Jackson Hole, 2022-08-26）— https://www.federalreserve.gov/newsevents/speech/powell20220826a.htm （查证 2026-11-18）

**二手（仅用于定位；结论已尽量回溯一手；标注【未核实】处为仅有二手）**

- **S6** Greenspan 2008-10-23 众议院监督委员会听证转录 — https://www.abc.net.au/am/archive/articles/2008/10/24/s2400016.htm （【未核实】）
- **S8** Greenspan 2014-11 CFR 访谈（CFR 未发布文字稿，SchiffGold 转述）— https://www.schiffgold.com/guest-commentaries/greenspan-gold-protects-you-from-unstable-currencies-audio-002 （【未核实】）
- **S10** Greenspan 2005-02-16 Humphrey-Hawkins 证词 "conundrum"（URL 未复核；常用出处 https://www.federalreserve.gov/boarddocs/hh/2005/february/testimony.htm ）（【未核实】原文未逐字核）
- **S14** Bernanke 2012-08-31 Jackson Hole 摘录（Reuters）— https://www.reuters.com/article/2012/08/31/usa-fed-bernanke-idUSL2E8JUBD120120831/ （【未核实】全文未取）
- **S17** Powell 2019-10-08 NABE 丹佛演讲报道（S&P Global）— https://www.spglobal.com/marketintelligence/en/news-insights/latest-news-headlines/powell-fed-to-grow-balance-sheet-soon-but-purchases-will-not-be-qe-54661877 （【未核实】）
- **S18** Bernanke 2013-05-22 证词 / 2013-06-19 记者会（NPR 转录）— 【未核实】未取官方原文
- **S19** 耶伦 2014-03-31 芝加哥演讲与 2014-08-22 Jackson Hole（Reuters/BI/Washington Examiner 转述）— 【未核实】
- **S20** J.P. Morgan AM, "FOMC Statement: October 2026", 2026-10-28 — https://am.jpmorgan.com/br/en/asset-management/adv/insights1/portfolio-insights/fixed-income/fixed-income-perspectives/fomc-statement-october-2026/ （查证 2026-11-18）
- **S21** NBG Global Markets Roundup, 2026-06-23 — https://www.nbg.gr/el/omilos/grafeio-tupou/reports/NBG-GlobalMarketsRoundup-23-06-2026 （查证 2026-11-18）
- **S22** Reuters（Fidelity 转载）2026-06-18：放弃前瞻指引、市场为加息定价 — 【未核实】
- **S23** Yonhap Infomax 2026-06-18：6 月声明措辞 — 【未核实】
- **S24** FA-Mag 2026-06-24：对沃什模糊反应函数的批评 — 【未核实】
- **S25** 新华社：Warsh 2026-05-22 宣誓就职；白宫仪式 — 【未核实】（转引自仓库 `docs/03-分析框架与模型设计.md`）
- **S26** 仓库内部：`docs/03-分析框架与模型设计.md:45-49`（政策三角）、`docs/24-原则库与当下研判.md`（债务/利息/美元份额）、`docs/23`（金价峰值）
- **S27** 本仓库代码与数据：`backend/app/ingest/providers/treasury.py`（名义/实际收益率与盈亏平衡）、`nyfed.py`（SOFR/EFFR）、`treasury_fiscal.py`（债务与 MTS）、`symbols.py`（DXY 与商品/股指）、`data/epic.db` 的 `macro_obs`/`market`

**中文辅助资料（仅作背景，未用于结论）**：中文媒体对格林斯潘 1966 年金本位文章与 2014 年"黄金是首要货币"的报道，均为二手转述，本笔记结论未依赖。

---

## 七、还没确定的（明确列出）

1. **1996 年演讲次日各国股市的具体跌幅**：广泛流传"日经 −3.2%"等数字，本笔记未找到可靠原始数据源，标"约"且不用于任何结论。
2. **格林斯潘 2005 年"conundrum"原句**：互联网引用极多，但未逐字核对证词原文（只核了 URL 存在性），引用时须谨慎。
3. **1966 年文章原文**：无官方免费版本，本笔记依据三个独立转载交叉比对；个别标点/断句可能与原版有差异。
4. **2014 年 CFR 访谈"Gold is a currency…"**：CFR 未发布文字稿，仅有音频与二手转述，标【未核实】。
5. **Bernanke 2012 Jackson Hole 全文**：仅取 Reuters 摘录；"grave concern" 的完整上下文未核。
6. **耶伦 2014 年"considerable slack"演讲全文**：仅二手转述。
7. **2013 taper tantrum 与 2008 危机的精确日频价格**：公开数值为常识性近似（10Y 1.6%→3.0%、S&P −57% 等），本仓库行情库不覆盖 2022 年前，未逐条核对。
8. **r\* 的当前估计**：HLW 模型需 FRED 数据（不可得），本笔记用 0.5–1.0% 的假设区间；所有"实际利率缺口"结论都依赖该假设。
9. **2026 年沃什的 FOMC 声明原文**：未从 federalreserve.gov 直接取（本笔记对该时期的引用全部来自二手，S20–S24）；若要做严格版本，应取 2026-06 与 2026-10 声明原文核对措辞。
10. **核心 PCE、失业率、M2、信用利差、FCI、房价**：本工具完全不可得，指标表中以代理替代，代理与真实值的方向一致性未做回测验证。
11. **"格林斯潘是否主张回归金本位"**：未找到任何一手原话支持"主张回归"；他的表述是"金本位在历史上提供了约束"与"黄金仍是最可靠货币"。若引用为"格林斯潘呼吁回归金本位"属误读。
12. **铜金比的数据单位**：`HG` 与 `XAUUSD` 在仓库中的原始单位未核对（铜报价量纲可疑），指标表中已改为"各自 z-score 后相减"以规避。
13. **2026 年 MTS 月度赤字的异常值**：2026-10 单月赤字 4,040 亿美元、利息 1,030 亿美元，量级偏高，可能含一次性因素，未核原始 MTS 表；"财政主导"相关推断应打折。
14. **沃什框架的完整文本**：2027 年会议日程调整、"任务组"设置均为二手报道，未见官方文件。

---

*本笔记只写这一个文件，未改动仓库其他任何文件。*
