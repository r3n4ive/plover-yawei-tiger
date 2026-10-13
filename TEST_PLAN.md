# 亚伟 Tiger + Plover 人工验收测试集

本文件是项目的完整人工回归测试集。它验证第三代亚伟 YW-V-3、Plover 5、
`yawei-tiger` system、`yawei-rime` extension、native 候选后端、可选 Rime 后端，
以及英文、符号、编辑和宏功能之间的兼容性。

每次修改 machine、system、extension、词库、候选逻辑、Rime schema 或配置文件后，
至少执行第 0、1、2、3、4、5、6、9、10 节。发布前执行全部章节。

## 0. 测试记录

### 0.1 测试环境

| 项目 | 值 |
| --- | --- |
| 日期 |  |
| Windows 版本 |  |
| Plover 版本 |  |
| 插件 commit / 安装方式 |  |
| 机器 | `Yawei V3` / `Keyboard` |
| system | `yawei-tiger` |
| extension | `yawei-rime` |
| 后端 | `native` / `rime` |
| 亚伟设备 | 第三代 YW-V-3 |
| 测试应用 | 记事本 / 浏览器文本框 / Word |

### 0.2 单项记录格式

每个失败或结果不稳定的项目单独记录：

| ID | 操作 | 预期 | 实际 | 复现次数 | 日志/截图 |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

故障报告必须包含：Plover 版本、后端、中文/英文模式、原始按键、Plover 显示的
canonical stroke、候选框状态、实际输出、是否重启后仍复现。

### 0.3 清理和观察原则

1. 每个用例开始前清空目标文本框，并确认光标在可输入位置。
2. 除非用例明确测试连续输入，不要在用例之间保留上一个 composition。
3. 候选后端测试同时观察三处：目标应用文本、Plover Paper/Output、候选窗口。
4. 记录“无输出”“输出错误”“多余空格”“候选顺序错误”“候选窗口状态错误”中的具体一种，
   不要只写“不能用”。

## 1. 安装、注册和启动

### 1.1 Python 和插件安装

在 Plover 自带 Python 中执行：

```powershell
& "C:\Program Files\Open Steno Project\Plover 5.4.1\data\python.exe" -m pip install -e ..\plover-multi-candidate -e .
```

预期：命令成功结束，没有覆盖 Plover 安装目录中的核心文件。

### 1.2 Plover 组件注册

在 Plover 设置中确认以下项目存在：

| 组件 | 预期名称 |
| --- | --- |
| Machine | `Yawei V3` |
| System | `yawei-tiger` |
| Extension | `yawei-rime` |

启用 extension 后重启 Plover。预期：Plover 能正常启动和退出，未连接亚伟时也不会卡死。

### 1.3 默认后端和 Rime 后端选择

默认 native 测试前，清除用户变量：

```powershell
[Environment]::SetEnvironmentVariable('PLOVER_YAWEI_BACKEND', $null, 'User')
[Environment]::SetEnvironmentVariable('PLOVER_YAWEI_RIME_ENABLE', $null, 'User')
```

重启 Plover。预期：默认使用 native；不会因缺少 Rime 而下载或启动 librime。

Rime 测试前设置：

```powershell
[Environment]::SetEnvironmentVariable('PLOVER_YAWEI_BACKEND', 'rime', 'User')
```

完全退出并重新启动 Plover。预期：扩展日志显示选择 `RimeBackend`；librime DLL、runtime 或
schema 初始化失败时，Plover 仍能启动，不得崩溃。DLL/构造阶段失败应回退 native/透明路线；
首次输入时才发现的 schema 错误应记录日志并把该 stroke 放回 Plover，若没有 native 词典则保持无输出。

## 2. 亚伟硬件和 machine

### 2.1 不启动厂商软件

1. 退出亚伟官方软件。
2. 启动 Plover，Machine 选择 `Yawei V3`。
3. 在 Plover Paper/Output 中按任意亚伟 chord。

预期：Plover 收到 stroke；目标应用不会把亚伟 HID 报告当成普通键盘字符。官方软件不应是必需进程。

### 2.2 设备枚举和重新插拔

1. 启动 Plover 后拔出亚伟，观察日志。
2. 等待 2 秒，再插回原 USB 口。
3. 重复一次换 USB 口的操作。

预期：日志先报告断开并进入重连；插回后自动恢复接收，不需要重启 Plover。
如果设备管理器显示“未识别的 USB 设备”，记录 USB 口、设备灯状态和 Plover 日志。

### 2.3 HID 原始按键方向

在 Plover 的 Paper/Output 逐项按下并记录 canonical stroke：

```text
左手：A- N- I- G- D- O- E- U- W- Z- B- X-
右手：-A -N -I -G -D -O -E -U -W -Z -B -X
组合：AO、GI、B-B、GI-GI、BX
```

预期：左右手不镜像、不交换列、不变成普通键盘字符；同一物理 chord 重复产生同一 canonical stroke。
`B-B` 和 `GI-GI` 必须保留为一个 chord 的左右手组合，不能被 machine 拆成两个 stroke。

### 2.4 无效 HID 报告和空报告

发布前用开发工具或已有 machine 测试夹具发送空报告、错误 marker、错误字段 tag、短报告。

预期：无效报告被忽略，不产生随机 stroke，不导致 machine 线程退出；正常报告随后仍能读取。

## 3. Plover 英文、符号和控制功能回归

保持英文/透明模式，用普通 Keyboard 或亚伟等价 chord 测试。所有操作都应由 Plover 原有字典处理，
不应被中文 backend 抢走。

### 3.1 英文词和空格

输入至少以下英文词和句子：

```text
the quick brown fox jumps over the lazy dog
lapwing plover keyboard
```

预期：英文单词正常上屏，词间按 Plover 原有规则自动空格；不出现中文候选框、Rime preedit 或 JSON 协议文本。

### 3.2 标点和常用符号

测试逗号、句号、问号、感叹号、引号、括号、斜杠、反斜杠、下划线、等号、加减乘除和货币符号。

预期：符号值和原 Plover 配置一致，前后空格规则一致。

### 3.3 Emily、Abby、Lapwing 功能映射

如果本机加载这些字典，分别测试：

| 功能 | 操作 | 预期 |
| --- | --- | --- |
| 左手修饰键 | Abby 左手 modifier 前缀 + 字母 | Ctrl/Alt/Shift/Win 正确作用于后一个键 |
| 固定前缀/后缀 | Emily/Abby 对应 outline | 前后缀仍能组合，不被中文模式误判 |
| 编辑 | 上下左右、Home、End、PageUp、PageDown | 光标移动正确 |
| 功能键 | F1、F5、F12 等已有映射 | 目标应用收到对应功能键 |
| 组合键 | Ctrl+C、Ctrl+V、Ctrl+Z、Alt+Tab | 系统快捷键正常执行 |
| 宏 | 一个已有宏或文本展开 | 只执行一次，不重复发送 |

### 3.4 特殊键和星键

测试本地符号表中使用星键的 outline，包含单星、多星兼容位置和星键前后组合。

预期：星键仍按实际物理位置归一化；不因“物理上存在多个兼容星键”而新增一个独立的 C 区或改变中文键位。

### 3.5 Plover 原生数字和编辑

在英文模式测试数字行、数字前缀、Backspace、Delete、Enter、Escape、Tab、Space。

预期：输出和原始 Plover 配置一致。候选选择用的 `XNE-*` 只有在中文模式且存在候选时才被 extension 消费。

## 4. 中文模式和路由边界

默认切换 chord：

```text
IUNE-IU  -> 进入中文模式
NEIU-IU  -> 设备报告反向顺序时也应进入中文模式
IU-IUNE  -> 回到英文模式
```

### 4.1 启动状态

Plover 完全重启后，不按模式键，直接输入英文词和普通 Plover 符号。

预期：启动默认为英文/透明模式；中文 backend 不消费普通 stroke。

### 4.2 进入和离开中文模式

1. 输入英文 `the`。
2. 按 `IUNE-IU`。
3. 输入一个中文编码。
4. 按 `IU-IUNE`。
5. 再输入英文 `test`。

预期：模式 chord 自身不产生乱码；模式 chord 不再执行旧词库的全局 `set_space`；中文提交不附加
自动空格，Plover 明确输出的空格/标点仍保留；切回英文后英文自动空格恢复。

### 4.3 控制/符号优先级

中文模式下先输入一个有候选的中文 outline，再输入 Plover 已拥有的符号、宏、方向键或快捷键 outline。

预期：Plover-owned outline 优先执行；extension 先确认/提交尚未完成的中文 composition，不能让后一个中文候选替换前一个
已由 Plover 输出的符号或宏结果。

### 4.4 未知 stroke 回退

中文模式下输入没有中文映射、也没有候选协议的 stroke。

预期：extension 不抛异常；stroke 回到 Plover 正常翻译流程。若 Plover 也无翻译，则无输出，不出现协议字符串。

## 5. Native 候选后端

本节要求清除 `PLOVER_YAWEI_BACKEND` 和 `PLOVER_YAWEI_RIME_ENABLE`，重启 Plover。

### 5.1 候选协议和词典加载

确认 `yw-native-candidates.json` 已启用，并排在单值中文词典之前。

预期：JSON 每个 key 仍只有一个字符串 value，候选 value 以 `=YAW-CAND:` 开头；不能把 JSON 改成一个 key 对应数组。
英文模式输入候选 outline 时，不得把 `=YAW-CAND:{...}` 原样输出。

### 5.2 多候选生成

依次输入以下 outline，记录候选顺序和候选数量：

| outline | 应至少看到的候选 |
| --- | --- |
| `BA-BA` | 爸爸、粑粑、巴巴、把把、叭叭、八八、坝坝 |
| `BDUEO-XIAO` | 通宵、通晓、同校、统销、通霄 |
| `GI-GI` | 积极、几集、唧唧、技击、几级、几季、鸡鸡、急急 |
| `A-BA` | 阿巴、阿爸、阿坝 |
| `A-BI` | 阿碧、阿鼻 |

预期：候选不重复；候选窗口只显示行缓冲中文和候选项，不显示拼音标签、物理键名或内部 JSON；同一 outline 重复输入结果稳定。

### 5.3 唯一候选和无候选

1. 输入一个当前词库中唯一的中文 outline，例如已有唯一单字 `ZIE-IUNEO`（“这”）。
2. 再输入一个无 candidate marker 的普通 Plover outline。

预期：唯一候选直接上屏，不弹候选框；无候选时交给 Plover。两种情况都不能残留上一次的 candidate state。

### 5.4 候选窗口显示规则

分别测试唯一候选、多候选、取消后空状态：

| 状态 | 预期窗口 |
| --- | --- |
| 多候选 | 显示 preedit 和候选列表 |
| 唯一候选 | 不显示候选弹窗，直接输出 |
| 取消 | 关闭窗口并清空 preedit |
| 选中 | 关闭窗口，输出一次选中项 |
| 新 outline | 上一个候选已确认，不被新候选回删 |

#### 5.4a 横排候选的数量变化与两行对齐（2026-10-11）

重启 Plover 加载更新，使用行缓冲模式 `XU-DZ`。

1. 打 `BA-BA`（爸爸），再打 `D-XGUA`（的话；`D-XGW` 也可）。
2. 继续交替输入这两个词几次，观察多候选与两候选的切换。
3. 按 `XU-X` 取消，再单独打 `D-XGUA`，检查重新出现的窗口。

预期：缓冲文字独占第一行；第二行从相同左边缘开始，依次紧邻显示
`1 的话`、`2 德华`。候选少时不得居中散开；文字无截断、无旧候选重叠；
隐藏/重开后两行高度仍正常。此项只验证显示，不改变候选排序或提交规则。

### 5.5 候选选择键

候选序号到亚伟 chord 的完整映射：

| 序号 | chord |
| ---: | --- |
| 1 | `XNE-W` |
| 2 | `XNE-U` |
| 3 | `XNE-E` |
| 4 | `XNE-GW` |
| 5 | `XNE-IU` |
| 6 | `XNE-NE` |
| 7 | `XNE-G` |
| 8 | `XNE-I` |
| 9 | `XNE-N` |

对 `BA-BA` 至少测试 1、2、4、9：

预期：只输出对应候选一次；选择后窗口关闭、状态清空；候选不足该序号时，chord 回到 Plover，不吞掉正常数字/符号映射。

如果当前 Qt 宿主能够把普通键盘事件转发给候选窗口，再额外测试数字 `1`～`9`、Enter、Escape、Up、Down、Left、Right、PageUp、PageDown；
候选窗口默认不抢目标应用焦点，因此普通键盘不是主验证路径，普通数字键未被窗口接收时应记录为宿主能力限制，不能判定亚伟选重失败。

### 5.6 Enter、Escape 和提交

1. 输入多候选 outline，按 Enter。
2. 输入多候选 outline，按 `XU-X`。
3. 输入部分候选后切换英文模式。

预期：Enter 提交当前首选；Escape 清空 composition 并撤回已嵌入首选；切换英文模式前自动提交当前中文，且不产生空格。

### 5.6a 亚伟确认上屏和强制上屏

在 Rime 后端（`PLOVER_YAWEI_BACKEND=rime`）下：

1. 输入 `I-XIN`、`I-I`、`I-I`，确认候选窗仍保留“一心一意”的整句 composition。
2. 按 `XNA-G`，预期目标应用一次性出现“一心一意”，不出现空格，候选窗清空。
3. 再输入同一句，按 `XNA-XW`，预期结果与确认上屏相同；这个键是独立的强制上屏绑定。
4. 输入中文后直接切回英文，或输入由 Plover 处理的标点/符号，确认中文先自动提交。
5. 输入中文后按 `XU-X`，确认 composition 和候选窗清空，目标应用不增加中文。

修改用户 `yawei_tiger.cfg` 的 `[commands]` 绑定并重启 Plover，重复上述测试，确认新的 chord 生效。

### 5.7 首选嵌入/顶屏

输入：

```text
BA-BA       -> 候选窗出现，应用先出现“爸爸”
XBA-XBA     -> “爸爸”保留，同时开始“妈妈/麻麻”等新候选
XNE-U       -> 将当前候选替换为第二项
```

预期：替换只删除当前候选已嵌入的文本；前一个词不会被多删；下一组输入会确认上一组首选。

### 5.8 音节边界、重复音节和长词

分别测试：

```text
BA-BA
GI-GI
BDUEO-XIAO / 后续下一组音节
```

预期：对称亚伟 chord 保留完整重复音节；不会把 `ba-ba` 吞成一个 `ba`；输入下一组时不会错误拼成长 preedit；
词库中确有完整长 outline 时，完整 outline 仍可命中完整词。

### 5.8a 前缀失配自动提交与重放

使用下面这组实际词典中的连续输入。`A-XDI` 有“阿里”候选，也有
`A-XDI/BA-BA -> 阿里巴巴` 等长词，但没有 `A-XDI/GI-GI`：

```text
A-XDI
GI-GI
```

保持 `[line_buffer] commit_on_prefix_miss = true`。

预期：`A-XDI` 的首选“阿里”先上屏；造成失配的 `GI-GI` 随后只处理一次，
成为“积极”等候选的新 token，不会丢失、重复或拼到“阿里”前一个长词后面。将该选项改为 `false` 后重试，
预期前一个 token 仍留在插件行缓冲中，直到显式提交或 Plover 外部命令边界才上屏。

完整行缓冲回归：

```text
GI-GI / GIN-XGIU / BA-BA
```

预期：三组分别形成“积极”“进取”“爸爸”，目标程序在按 `XNA-G` 前不增加任何文本；
按下后一次性得到“积极进取爸爸”。这组输入不是前缀失配测试，不能因为词间已经定界就提前提交整行。

### 5.9 词/短语首末字辅码筛选

使用 `BDUEO-XIAO`：

1. 先输入拼音 outline，确认候选包含“通宵、通晓、同校”。
2. 输入左手虎码辅码，只筛首字。
3. 输入右手虎码辅码，只筛末字。
4. 同时按左右辅码，确认两端同时筛选。

预期：左右筛选互不误伤；筛到唯一候选立即上屏；不匹配时保留可诊断状态或明确无候选，不把错误词输出。

### 5.10 连续辅码、退格和运行时规则

在候选出现后连续输入两位辅码，再按中文单字符退格键 `IUO`（设备日志可能显示为 `IOU-`）。

预期：只撤回最后一位辅码，候选恢复到上一筛选状态；再次按退格可撤回上一位；没有 composition 时才交给目标应用。

修改用户配置文件中的某一个虎码字母映射或字符规则，重启 Plover 后重复同一测试。

预期：运行时配置生效，不需要修改生成的候选 JSON；配置重启前不应半生效。

## 6. Native 编辑、撤销和 Plover 回退

### 6.1 命令映射表（当前均为临时测试绑定）

以下 chord 只用于当前开发和人工验收。最终键位要等中文音节、英文方案、符号和编辑功能完成后统一分析冲突，再重新决定。

| 亚伟 chord | 命令 | 预期 |
| --- | --- | --- |
| `IUO`（设备可显示 `IOU-`） | Backspace | 候选中退一步；无候选时删一个字符 |
| `GWNE`（设备可显示 `NGEW-`） | Delete | 候选中取消；无候选时右删一个字符 |
| `W-DG` | Ctrl+Backspace / 中文整词退格 | 有 native 历史时精确删除最近插件词；否则交给目标应用 |
| `GWNE-X`（设备可显示 `NGEW-X`） | Ctrl+Delete | 有候选时先取消；否则交给目标应用 |
| `DG`、`DG-`、`-DG` | native undo | 删除最近一次 native 词；无 native 历史时回退 Plover `=undo` |
| `XU-X` | Escape/cancel | 只取消候选或 composition，不删除普通光标文本 |

### 6.2 单字符和整词删除

1. 输入唯一单字“这”，按 `IUO`。
2. 输入“爸爸”，按 `IUO` 一次。
3. 重新输入“爸爸”，按 `DG`。
4. 再输入“爸爸”，按 `W-DG`。

预期：`IUO` 每次只退一个编辑单位；`DG` 对插件记录的双字词一次删除整词；`W-DG` 的目标应用行为与 Ctrl+Backspace 一致。

### 6.3 候选状态下编辑

候选窗打开时分别按 `IUO`、`GWNE`、`W-DG`、`GWNE-X`、`DG`、`XU-X`。

预期：候选状态优先处理，不把控制键误发给目标应用；取消后状态清空；没有候选时才执行普通编辑命令。

### 6.4 Plover 历史回退

输入一个由 Plover 普通字典输出的英文词或符号，再在中文模式下按 `DG`，然后在没有 native 历史时重复按 `DG`。

预期：native 没有可撤销内容时不吞命令，Plover 的原生 undo/history 仍有机会执行；不能误删中文之外的文本。

## 7. Rime 整句后端

本节先设置用户变量并重启 Plover：

```powershell
[Environment]::SetEnvironmentVariable('PLOVER_YAWEI_BACKEND', 'rime', 'User')
```

Rime 后端使用项目隔离目录，不应读写小狼毫 `%APPDATA%\Rime` 用户配置。

### 7.1 Runtime、schema 和词典

第一次启动 Rime 路线时观察日志和目录：

```text
%LOCALAPPDATA%\Plover\yawei-rime\runtime
%LOCALAPPDATA%\Plover\yawei-rime\data\shared
%LOCALAPPDATA%\Plover\yawei-rime\data\user
```

预期：librime runtime 下载后通过 SHA-256 校验；schema 和词典编译成功；失败时回退且 Plover 不退出。
不应修改 Weasel/Rime 用户目录。

### 7.2 连续音节和整句

输入：

```text
I-XIN  I-I  I-I
```

预期：Rime composition 形成 `yixin'yi'yi`，候选中出现“一心一意”；选择或提交后输出“一心一意”，不附加空格。

### 7.3 Rime 候选顺序和整句排序

逐项测试：

| outline | 预期至少存在 |
| --- | --- |
| `BA` | 把、巴、爸爸等候选 |
| `BDUEO-XIAO` | 通宵、通晓、同校、统销等 |
| `GI-GI` | 积极、几集、唧唧、技击等 |
| `I-XIN` | 一心、易信、疑心等 |

预期：Rime 候选框显示的是词语/字，不是 Plover 协议字符串；候选顺序由 Rime schema/词典决定，不能用 native 顺序作为判断标准。

### 7.4 Rime 选重、翻页和取消

在有多个候选的编码下测试普通数字键、`XNE-*`、Enter、Escape、PageUp、PageDown。

预期：候选选择调用 Rime 当前 page；Escape 清空 composition；Enter 提交当前项；翻页只改变候选页，不输出额外空格。

### 7.5 Rime 退格和切换模式

1. 输入两个或三个音节后按 `IUO`。
2. 输入一段中文 composition 后按 `IU-IUNE`。
3. 切回英文后输入英文词。

预期：退格由 librime editor 处理；切换前调用 composition commit；中文提交没有模拟空格；英文自动空格恢复。

### 7.6 Rime 与 native 的区分测试

用 `BNA-INEO` 做反向测试：

- native 路线：按当前 native 词库结果处理，不应出现 Rime 的额外候选；
- Rime 路线：按 `bani` 组合进入 Rime 候选，候选内容和排序可能不同。

若两种路线结果完全相同，必须结合日志确认 backend 类型，不能只凭屏幕文字判断。

### 7.7 Rime 失败回退

临时把 `PLOVER_YAWEI_RIME_DLL` 指向不存在文件，或暂时改用不存在的 schema id，重启 Plover。

预期：日志记录 Rime 初始化失败；Plover 仍能启动。无效 DLL 在构造阶段失败时应回退 native/透明；
无效 schema 可能在首次输入时才失败，此时该 stroke 应回到 Plover，若没有 native 词典则保持无输出。
恢复正确配置并重启后 Rime 可再次使用。

### 7.8 外挂拼音输出模式

关闭 Plover 后，在用户配置目录的 `yawei_tiger.cfg` 增加：

```ini
[backend]
mode = external_pinyin
```

重新启动 Plover，并确认日志出现 `using external pinyin output backend`。打开系统 Rime
或其他拼音输入法，进入中文模式后输入：

```text
BA-BA
XBA-XBA
```

预期：Plover 不弹自己的候选窗，目标输入法收到两组拼音组合（分别相当于 `ba'ba`、
`ma'ma`），候选和整句排序由目标输入法显示。输入 `XNA-G` 时，预期向目标输入法发送
确认键并上屏当前候选；输入 `XU-X` 时，预期清除外部输入法的当前组合。日志中的 backend
必须是 `PinyinOutputBackend`，不能是 `NativeCandidateBackend` 或 `RimeBackend`。

继续在外部组合未确认时按 `IUO` 一次。预期：外部输入法只删除当前组合的最后一个拼音字符，
不会把整句或目标程序中已经上屏的文字删除；随后再输入一个音节时，组合分隔符和候选状态
仍然正确，没有重复撇号或丢失音节。

将目标程序中光标放到一个字符前面，再按 `GWNE`。预期：Plover 向目标程序发送一次
前向 Delete，光标右侧的字符被删除；日志出现 `Yawei forwarding target key=DELETE`。
`GWNE` 不会删除光标左侧字符，也不会删除外部输入法的拼音组合；光标在行尾时没有可见
变化是正常的。组合状态会被清空，下一次输入从新的拼音组合开始。`IUO` 才是组合中的
退格。`W-DG`、`GWNE-X` 和 `DG` 仍交给 Plover 的整词删除、整词前移/后移和撤销逻辑。

在外部拼音组合存在时分别按一次 `W-DG`、`GWNE-X`、`DG`。预期：外挂后端先确认 QQ
当前组合，再分别发送 `Ctrl+Backspace`、`Ctrl+Delete`、`Ctrl+Z`；三者都不应让 QQ
选中整段拼音或产生额外撇号，`DG` 连按也应连续撤销。`XU-X` 应发送 Escape 取消组合。

出现 QQ 候选框后，按 `XNE-W`、`XNE-U`、`XNE-E`。预期：外挂后端分别发送数字 `1`、`2`、
`3` 给 QQ，候选由 QQ 上屏；Plover 不弹自己的候选窗，也不输出字面数字。

测试结束后删除该 `mode` 配置或改回 `native`，重启 Plover，确认 native 候选窗恢复。

## 8. 配置文件、词库和构建工具

### 8.1 26 个虎码辅码键配置

确认用户配置目录或包内默认文件存在：

```text
yawei_tiger.cfg
```

检查 `[auxiliary_keys]` 中的 26 个字母映射。复制一份配置，只改一个未使用的 chord，重启 Plover 并用对应辅码测试。

预期：新的物理 chord 生效；原 chord 不再触发该字母；与拼音 chord 重叠时应在日志中报冲突，不能静默覆盖拼音。

### 8.2 虎码字符规则文件

确认独立规则文件存在：

```text
tiger2.txt
```

修改一个字符的虎码编码，重启后测试候选筛选。预期：规则变化影响筛选，不需要重建 Plover JSON。

### 8.3 Native 候选词典构建

在仓库根目录执行：

```powershell
& "C:\Program Files\Open Steno Project\Plover 5.4.1\data\python.exe" tools\build_native_candidates.py
```

检查：

1. 输出候选组数量和写入路径。
2. JSON 是合法对象。
3. 每个 value 是字符串，不是数组。
4. 标记值以 `=YAW-CAND:` 开头。
5. `BDUEO-XIAO` 仍能生成通宵、通晓、同校等候选。

### 8.4 Rime 兼容词典同步

执行：

```powershell
& "C:\Program Files\Open Steno Project\Plover 5.4.1\data\python.exe" tools\rime\sync_dictionary.py --check
```

预期：同步检查通过；Rime YAML 使用 `code text` 格式，不能反向替代 native JSON 源文件。
修改源 JSON 后再执行同步，确认 Rime 词典内容变化。

### 8.5 词库优先级和协议过滤

临时在普通字典中加入一条与 candidate marker 相同 outline 的普通值，重启并测试。

预期：词库优先级和 shadowing 行为符合当前构建规则；普通 Plover lookup 不应输出 marker JSON；恢复文件后再次测试。

## 9. 生命周期、异常和恢复

### 9.1 Plover 停止和重启

在候选窗打开、Rime composition 未提交、亚伟正在输入三个状态下分别退出 Plover，再重启。

预期：Plover 能退出，不被 HID read 或 Qt 窗口阻塞；重启后 backend 状态清空，不残留旧候选或旧文本。

### 9.2 候选窗口异常

候选框打开时切换到另一个窗口、最小化 Plover、关闭目标应用，再恢复目标应用。

预期：候选窗不会成为键盘输入目标；目标应用仍收到选择结果；窗口关闭后再次输入能重新创建。

### 9.3 配置或词典损坏

在备份后临时使用格式错误的 cfg、缺失 tiger2.txt、损坏的 candidate JSON 或不存在的 Rime schema。

预期：错误被记录并回退到透明/native 可用路径；不应把 traceback 文本输出到目标应用。恢复备份后重启即可恢复。

### 9.4 USB 设备恢复

输入过程中拔出亚伟，再插回；重复一次在 Plover 正在候选窗状态下拔出。

预期：不会死锁；设备恢复后能继续产生 stroke；未完成 composition 的处理结果要么明确取消，要么明确保留，不能产生乱码或重复提交。

## 10. 发布前完整回归顺序

按以下顺序执行并记录结果：

1. 0：记录环境，确认测试变量。
2. 1：安装、entry point、默认 native/Rime 选择。
3. 2：设备枚举、方向、拔插恢复。
4. 3：英文、符号、Emily/Abby/Lapwing、快捷键、编辑和宏。
5. 4：中文模式、控制优先级、未知 stroke 回退。
6. 5：native 候选、唯一/多候选、窗口、选择、辅码和顶屏。
7. 6：Backspace、Delete、整词、undo、Escape 和 Plover 回退。
8. 7：Rime runtime、连续音节、整句、选重、翻页、退格、无空格提交和失败回退。
9. 8：cfg、虎码规则、JSON 构建、Rime 同步和协议过滤。
10. 9：退出、候选窗、损坏配置和 USB 恢复。

### 10.1 结论分类

- `通过`：符合预期，可进入日常使用。
- `可用但需优化`：主流程可用，但候选排序、延迟、词库覆盖率或窗口体验需要后续改进。
- `阻塞`：硬件无法读取、Plover 无法退出、模式无法切换、中文提交重复/吞字、英文功能回归或 Rime/native 都无法启动。

优先级：硬件读取和退出 -> 英文/符号兼容 -> 模式切换 -> 中文不重复/不吞字 -> 候选选择 -> 辅码筛选 -> Rime 整句 -> 排序、词库覆盖率和性能。

## 11. 自动测试对应关系

人工测试发现问题后，可用下面的自动测试定位范围：

| 人工范围 | 自动测试文件 |
| --- | --- |
| machine/HID 解码 | `tests/test_machine.py` |
| extension 路由和模式 | `tests/test_extension.py`、`tests/test_routing.py` |
| Plover 5 完整启动、实验词库切换和恢复 | `tests/test_plover_startup.py` |
| 独立候选插件：词边界、Plover 编辑同步、命令配置及卸载钩子 | 候选仓库 `tests/test_multi_candidate_extension.py`、`tests/test_plover_startup.py` |
| native 候选、辅码、顶屏、undo | `tests/test_native_candidates.py` |
| 候选窗口控制器 | 候选仓库 `tests/test_candidate.py` |
| Qt 实际布局、字体、候选增减、单/双行切换与背景绘制 | 候选仓库 `tests/test_candidate_window.py` |
| 候选窗设置面板、实时应用和用户配置备份 | 本仓库 `tests/test_candidate_window.py`；候选仓库 `tests/test_candidate_window.py`、`tests/test_window_settings.py` |
| Rime backend、连续音节、无空格 commit | `tests/test_rime_backend.py`、`tests/test_factory.py` |
| 外挂拼音输出、模式选择 | `tests/test_pinyin_backend.py`、`tests/test_extension.py`、`tests/test_factory.py` |
| runtime 下载/隔离编译 | `tests/test_librime_runtime.py` |
| chord 到拼音/虎码映射 | `tests/test_stroke_mapping.py` |
| JSON/Rime 词库构建 | `tests/test_build_dictionary.py`、`tests/test_build_native_candidates.py` |
| E 迅手册语义 adapter（声韵码、声调筛选、行缓冲） | 候选仓库 `tests/test_exun_adapter.py`、`docs/exun-reference-adapter.md` |

代码回归命令：

```powershell
& "C:\Program Files\Open Steno Project\Plover 5.4.1\data\python.exe" -m pytest tests -q
```

自动测试通过不能替代第 2、3、7、9 节的真实设备、真实窗口和真实目标应用测试。

## 12. 可选词频词库验收

本节只测试多候选排序，仍走 native JSON，不启用 Rime。正式词库保留原始顺序。

验收记录：2026-10-12 用户已确认当前实验表输入与选重正常，本节测试通过。

### 12.1 启用和重启

将生成的 `yw-native-candidates-wanxiang.json` 放到用户词典目录，在用户
`yawei_tiger.cfg` 添加：

```ini
[native_candidates]
path = yw-native-candidates-wanxiang.json
```

完全退出后重新启动 Plover。日志中最终的 `candidate_table` 应指向该文件；
当前实验表的 `weighted_multi_candidate_groups` 是 `35972`。扩展只启动一次，
不能有 `initializing extension` 错误或候选协议字符串漏到目标程序。

### 12.2 最小人工测试

在空白记事本文档中按 `IUNE-IU` 进入中文模式，用 `XU-DZ` 确认行缓冲模式。

1. 按 `A-BA`：候选前三项应是“阿爸、阿坝、阿巴”，缓冲首选是“阿爸”。
   原始词库的前三项是“阿巴、阿爸、阿坝”，这个用例可以判断词频表是否生效。
2. 按 `XNE-U` 选第二项：缓冲变成“阿坝”，记事本还没有文字。
3. 按 `XNA-G` 提交：记事本得到“阿坝”，缓冲和候选清空。

可选检查：`BA-BA` 首选仍是“爸爸”；`BDUEO-XIAO` 前三项仍是“通宵、通晓、同校”。
这两个编码的排序没有变化，单独用它们不能证明实验词库已启用。

### 12.3 恢复默认

清空 `[native_candidates]` 的 `path` 后完全退出并重新启动 Plover。
`A-BA` 应恢复“阿巴、阿爸、阿坝”；正式候选词典重新启用，实验表禁用。
其他词典、行缓冲模式、符号和编辑键继续保持原配置。

## 13. 独立候选插件的自动验收

这一节用于将候选功能独立打包后的兼容性检查。当前亚伟输入已使用共享核心，
不需要在本机再启用 `multi-candidate`，也不需要重复第 12 节的人工操作。

2026-10-13：候选源码、独立测试和 E 迅参考 adapter 已迁到 `plover-multi-candidate` 仓库。本仓库只保留中文/HID/理论适配测试；先安装本地候选包后分别运行两个项目的测试。中文仓库 175 项、候选仓库 75 项通过；两个 wheel 与源码包构建通过。候选 wheel 在禁止亚伟/HID 导入的隔离环境中通过全部 75 项测试。用户配置、辅码与实验词库文件哈希均未变化。

使用小型测试词典和无输出副作用的设备适配，自动验证：

1. 完整 Plover 启动后能识别候选协议，协议文本不会交给 Plover formatter。
2. 前一个词仍是长词前缀、后一笔开始新词时，按配置提交或保留前词；后一笔只重新处理一次。
3. 候选选择与行缓冲提交不重复输出；无候选时，原来的数字映射仍有效。
4. 方向键或快捷键交给 Plover 前先同步缓冲；外部编辑之后，插件不再按旧文本长度回删。
5. 强制解绑保留短词、阻止长 outline 合并；未完成前缀不会被解绑键丢弃。
6. 已有的整词撤销、提交及目标侧删除可以独立配置，重复/未知绑定写入日志。
7. Qt 窗口收到实时候选和缓冲更新，遵守固定位置配置，提交后收起。
8. 停止扩展后移除 hook 和协议过滤器；独立 wheel 可从自身路径导入，不依赖亚伟代码。

2026-10-12：全套自动测试 237 项通过，独立 wheel 构建通过。真实设备验收结果
仍以各人工章节为准；本节不表示新增硬件支持或已经发布到 PyPI。

## 14. 候选窗图形设置

首次安装新菜单入口后，完全退出并重新打开 Plover。后续调整外观不需要再重启。

最小人工测试：

1. 打开 Plover 的 **工具 → 亚伟候选窗设置**。把“候选字号”调大，确认下方预览随之变大。
2. 选择“固定在屏幕位置”，固定位置选“右下”，点击“保存并应用”，然后关闭设置面板。
3. 在记事本按 `IUNE-IU` 进入中文、`XU-DZ` 进入行缓冲，再按 `BA-BA`。
   候选窗应在屏幕右下，字号为刚才设置值；缓冲仍显示“爸爸”，记事本没有提前收到文字。
4. 按 `XNA-G` 提交，只输出一次“爸爸”。

可选检查：把位置方式改回“跟随输入光标”并保存，再打 `BA-BA`，应跟随输入位置。
只改预览后关闭不保存，实际候选窗应继续采用之前已保存的设置。“恢复默认”也需要
点击“保存并应用”才会生效。

自动验证已覆盖：保留模式/词频表路径/辅码/其他用户配置与注释、备份上一个版本、
首次复制默认配置而不写包文件、原子写入失败恢复、当前候选和行缓冲保留、已提交文本
不重复输出、损坏配置/无效颜色不应用。亚伟与独立候选扩展共用同一套设置面板。

本节人工验收待用户执行，不把自动测试作为实际菜单和目标程序的人工验证结果。

2026-10-12：全套 249 项自动测试通过；本机菜单 entry point 已安装并由 Plover registry
识别；独立 wheel 中的面板、预览和配置保存也通过了不导入亚伟代码的隔离验证。

## 15. 两个项目拆分后的迁移检查

包拆分保留配置路径、当前控制 stroke 和候选协议。两个仓库的安装步骤见 README；无需重新生成用户词库或覆盖 `yawei_tiger.cfg`。

1. 完全退出并重新打开 Plover，确认机器仍是 `Yawei V3`，system 是 `yawei-tiger`，启用 `yawei-rime`。
2. 不额外启用 `multi-candidate`。在空白记事本按 `IUNE-IU`、`XU-DZ`、`BA-BA`，缓冲显示“爸爸”，目标程序无文字。
3. 按 `XNA-G`，只上屏一次“爸爸”。
4. 打开“工具 → 亚伟候选窗设置”，确认原字体/位置设置仍被读取。

这组检查验证迁移，不要求重复已通过的全部词频、数字和辅筛测试。人工结果待用户确认。
