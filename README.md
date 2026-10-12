# plover-yawei-tiger

这是一个在 Plover 上使用中文的亚伟速录方案。中文输入不可避免会遇到同音字和多候选，本项目用“拼音码 + 虎码辅码”构建词库，把候选筛选也纳入速录击键中。

> 当前默认路线是纯 Plover native 候选后端，不需要安装或启动 Rime。Rime/librime 只在明确选择时作为兼容实验使用。

## 当前状态

- Plover 5.4.1：已适配。
- 硬件：支持第三代亚伟 `YW-V-3` HID machine，可不启动厂商软件读取键盘。
- 中文：支持多候选、数字选重、首选嵌入/顶屏、虎码首末字筛选、连续辅码和中文行缓冲。
- 候选窗：缓冲文本单独一行，候选横向排列；候选数量变化时保持左对齐，不会出现两行错位、旧候选重叠或文字裁切。
- 配置：26 个虎码辅码键位和字符规则可以通过用户文件修改。
- 回归测试：`180 passed`；真实亚伟设备和目标应用仍需要人工冒烟测试。

## 实际输入界面

下面是当前 native 候选窗的实际渲染效果。候选窗不是 Plover 默认的列表对话框，而是贴近速录输入的两行浮层：

**多候选：输入 `BA-BA`（爸爸）**

![输入爸爸后的多候选窗口](docs/images/multi-candidate-selection.png)

**行缓冲：先输入“爸爸”，再输入“的话”**

![行缓冲中的候选窗口](docs/images/line-buffer-candidate.png)

第一张图展示候选数字和当前首选；第二张图展示已缓冲文本与当前候选分行显示。候选数量变化时，候选项仍从左侧固定间距排列，窗口不会重新把候选均匀拉开。

## 亚伟键盘支持

项目支持第三代亚伟 YW-V-3 硬件键盘。安装本项目和 `hidapi` 后，在 Plover 中将机器选择为 `Yawei V3`，即可直接读取亚伟键盘的 HID 报告；普通键盘模拟仍可选择 `Keyboard`。

## 安装和运行时路由

本项目正在把中文候选能力做成 Plover 插件，而不是要求用户修改 Plover 安装目录。安装开发包后，Plover 会注册以下组件：

- `Yawei V3` machine：读取第三代亚伟 HID 键盘；
- `yawei-tiger` system：当前拼音 + 虎码辅码键位系统；
- `yawei-rime` extension：为中文后端提供翻译前路由；
- 现有 Plover 字典：符号、宏、修饰键、方向键和英文仍由 Plover 处理。

默认启用纯 Plover 候选后端。Rime 后端代码保留为可选的整句输入路线；只有明确设置
`PLOVER_YAWEI_BACKEND=rime` 或在配置中写 `mode = rime` 时才会尝试启动，失败后回退到
native，不会悄悄改变普通 Plover 路由。旧的 `PLOVER_YAWEI_RIME_ENABLE=1` 只保留给直接调用
兼容工厂，不会自动接管正常启动。纯 Plover 后端会自动识别值以 `=YAW-CAND:` 开头的词条，不修改
Plover 核心，也不改变普通 JSON 词条的含义。新协议说明见
[docs/native-candidate-protocol.md](docs/native-candidate-protocol.md)。

后端模式也可以写在用户配置目录的 `yawei_tiger.cfg` 中：

```ini
[backend]
# native：即时纯 Plover；line_buffer：中文行缓冲；
# external_pinyin：只输出拼音/辅码，由系统 Rime 或其他输入法选词。
mode = line_buffer
```

也可以用 Plover 插件市场中的 `plover-dict-commands` 通过并击切换模式。Yawei 扩展会自动加入三本空的模式标记词典，并监听它们的启用状态；这些词典不包含任何翻译，不会污染普通词库。默认开发按键为：

| 模式 | 默认 chord | 作用 |
|:---|:---|:---|
| native | `XU-DG` | 即时原生候选，首选立即输出 |
| line_buffer | `XU-DZ` | 中文行缓冲，确认后整行上屏 |
| external_pinyin | `XU-DW` | 只输出拼音/辅码，由系统输入法选词 |

按键只在 Yawei 扩展启用时由扩展消费。若安装了 `plover-dict-commands`，实际切换使用它的
`TOGGLE_DICT` 命令；旧版或未加载该插件时，扩展提供等价的本地回退。可以在 `yawei_tiger.cfg`
中修改 `[mode_strokes]`，模式标记词典文件名可在 `[mode_dictionaries]` 中修改。切换会先提交当前候选或行缓冲，再重建对应后端。

`PLOVER_YAWEI_BACKEND` 环境变量优先于配置文件，可取 `native`、`immediate`、
`line_buffer`、`external_pinyin` 或 `rime`。其中 `native`/`immediate` 关闭行缓冲，
`line_buffer`/`buffered` 打开行缓冲；`external_pinyin` 不加载 librime，也不显示 Plover
候选窗；它通过 Plover 的文字输出发送拼音，连续音节以 `'` 分隔，辅码直接接在当前音节后面。
因此可以把系统 Rime、QQ 拼音或其他输入法当作外部候选引擎，同时保留 Plover 的 machine、
英文词典、符号和编辑路由。外挂模式仍可使用同一套亚伟数字选重键：`XNE-W` 到 `XNE-NE`
分别发送数字 `1` 到 `6`，`XNE-G`、`XNE-I`、`XNE-N` 对应 `7`、`8`、`9`；候选排序和整句
逻辑仍由外部输入法负责。

由 `python tools/build_native_candidates.py` 从当前 `base.json` 生成的候选词典
已加入亚伟系统默认词典，并排在单值汉字词典之前。它把旧的“拼音 outline + 虎码后缀”
合并为拼音 outline 下的候选组。候选筛选默认读取独立的
`theory_map/tiger2.txt` 字符规则，不需要重建候选词典；候选 JSON 中保留的 `chars`
字段只作为兼容回退。

26 个虎码辅码键位默认配置在 `yawei_tiger.cfg`。安装或开发启动时，扩展优先读取
`%LOCALAPPDATA%\\plover\\plover\\yawei_tiger.cfg` 和
`%LOCALAPPDATA%\\plover\\plover\\yawei_tiger_aux.txt`，再回退到包内默认文件。
修改这两个用户文件并重启 Plover，即可更换物理 chord 或虎码规则；也可以分别用
`PLOVER_YAWEI_AUX_MAP`、`PLOVER_YAWEI_AUX_CODES` 指定其他文件。

在 Plover 的插件设置中启用 `yawei-rime` 后，扩展会在当前 engine 实例上安装一个可撤销的
兼容钩子。这个 entry point 名称是历史兼容名称；当前默认中文路线是纯 Plover 候选后端。
它不会覆盖或改写 Plover 的安装文件；当前开发目标是 Plover 5.4.1。停用扩展后会恢复
原始流程。没有候选词典时扩展是透明的，所有 stroke 都回退到 Plover。

本地开发安装会直接注册为 Plover 的 `yawei-rime` extension、`Yawei V3`
machine 和 `yawei-tiger` system。Plover Plugin Manager 的在线列表来自 PyPI
和 Open Steno 插件注册表；未发布到 PyPI 并登记前，在线列表不会显示本项目，
但不影响本地 entry point 被 Plover 加载。

候选 UI/state/token buffer、候选协议解析、outline 前缀索引、理论无关的 `CandidateFilter`
接口和候选组合状态机已抽到 `plover_multi_candidate` 共享包。Yawei 适配层提供 `=YAW-CAND:`
标记、中文普通词条识别和 Tiger 筛选；旧的 `NativeCandidateBackend` 导入路径仍兼容。共享包
目前仍与 Yawei 同包发布，还不是可单独安装启用的 Plover extension。测试中已用虚构的非 Yawei
适配器走通独立 marker、筛选、行缓冲和提交；这只验证共享接口，不代表已支持另一套真实理论。
独立发布前仍应接入一套实际理论，并明确哪些行缓冲提交策略由插件配置、哪些属于理论策略。模块归属见
[组件归属与拆分边界](docs/component-ownership.md)。

共享候选插件现在有独立的打包项目：
`packaging/plover-multi-candidate`。它注册通用的 `multi-candidate` extension，
只处理 `=PLOVER-CAND:` 候选协议、候选框和可选行缓冲，不包含亚伟键位、虎码辅码或中文空格规则。
独立插件的配置和构建方式见
[独立多候选插件说明](docs/independent-multi-candidate-plugin.md)。

Rime 后端默认不启用；相关运行时和生成文件只在显式选择该路线时使用。设置
`PLOVER_YAWEI_BACKEND=rime` 后，它会从 librime 官方发布页下载并校验固定版本
`1.17.0`（Windows MSVC x64），缓存到 `%LOCALAPPDATA%\Plover\yawei-rime`。
项目自带的 schema 和词典会安装到同一目录下的隔离 Rime 数据目录，不读取或修改
小狼毫的 `%APPDATA%\Rime`。也可以用 `PLOVER_YAWEI_RIME_ROOT` 指定缓存位置，
或用 `PLOVER_YAWEI_RIME_DLL` 指定开发用 DLL；`PLOVER_YAWEI_RIME_USER_DIR` 和
`PLOVER_YAWEI_RIME_SCHEMA` 可覆盖用户目录和 schema。下载、校验或初始化失败时，
扩展会记录日志并保持 Plover 原有行为。

候选窗口会在原生后端产生 preedit 或候选时显示，并保持在前台。第一行是行缓冲文本，
第二行是候选项；候选项从左侧以固定间距排列，候选数量减少时不会被 Qt 均匀拉开。
刷新时旧标签会立即隐藏，窗口高度根据当前字体和两行内容重新计算，因此不会出现“爸爸”正常、
“的话”两行错位或候选文字上下被裁切的问题。窗口宽度是最小宽度，不会把少量候选强行分散到整行。

候选窗位置可以在用户配置的 `[candidate_window]` 中设置：

```ini
position_mode = follow
fixed_position = bottom_left
margin = 12
```

`position_mode = follow` 会让窗口跟随当前输入光标；Windows 读取不到系统插入光标时，
会回退到鼠标位置。也可以使用 `position_mode = fixed` 固定到屏幕工作区的八个位置：
`top_left`、`top_center`、`top_right`、`middle_left`、`middle_right`、
`bottom_left`、`bottom_center`、`bottom_right`。例如：

```ini
position_mode = fixed
fixed_position = top_right
margin = 20
```

候选选择使用亚伟左手
`XNE` 前缀，右手采用 Lapwing 的九键数字布局，落在亚伟右手较自然的 `W/U/E`、
`G/I/N` 三列；最内侧的 `D/Z` 列不参与选重：

| 候选序号 | 亚伟 chord |
|:---:|:---|
| 1 | `XNE-W` |
| 2 | `XNE-U` |
| 3 | `XNE-E` |
| 4 | `XNE-GW` |
| 5 | `XNE-IU` |
| 6 | `XNE-NE` |
| 7 | `XNE-G` |
| 8 | `XNE-I` |
| 9 | `XNE-N` |

例如候选框显示“1. 你、2. 尼、3. 妮”时，按 `XNE-W` 上屏“你”，按 `XNE-U`
上屏“尼”，按 `XNE-E` 上屏“妮”。`XNE-GW`、`XNE-IU`、`XNE-NE` 是 Lapwing
数字布局中的 4、5、6 组合键。
这组指法只在中文模式且当前确实有对应候选时被插件消费；没有候选时会回到 Plover 原来的翻译，
因此不会改变亚伟基础指法。候选窗口仍支持普通键盘的数字 1-9、Enter、Escape、
方向键和翻页键；这些操作调用同一套 backend 命令。

候选命令仍可由下游方案覆盖，例如调用 `set_command_stroke("某个空闲 chord", "select", 0)`。
项目默认不预留新的亚伟编码空间，便于以后替换拼音、辅码或词库而不产生固定冲突。

### 中文整句上屏

中文整句不会在每个音节后立即提交，而是交给 Rime 保留在 composition 中，等句内排序稳定或遇到边界再上屏。默认有两个独立的确认键：

- `XNA-G`：确认上屏，提交当前高亮候选；没有手动选重时就是当前首选。
- `XNA-XW`：强制上屏，当前版本同样提交当前高亮候选，但单独保留绑定，便于以后实现自动顶屏模式。

以上确认、编辑和撤销 chord 都是当前开发阶段的临时测试绑定，不代表最终键位方案。最终方案会在中文音节、英文 Lapwing、符号和编辑功能全部完成后统一做冲突分析，再决定是否保留或更换。它们都可以在 `yawei_tiger.cfg` 中修改，用户配置目录中的同名文件优先于包内默认值。切回英文、输入 Plover 自己处理的标点/符号/宏/编辑键时，插件也会先自动提交当前中文 composition；`XU-X` 仍然是取消，不会上屏。这样正常输入整句时无需逐词手选，只在确实需要改候选时使用数字选重，最后用确认键提交整句。

### 运行测试

测试必须使用 Plover 自带的 Python 环境，因为 machine 和插件依赖 Plover 的运行时包：

```text
"C:\\Program Files\\Open Steno Project\\Plover 5.4.1\\data\\python.exe" -m pytest tests -q
```

测试不需要连接亚伟硬件；HID 报告和 Rime 通信均有模拟覆盖。真实设备仍建议在发布前做一次人工冒烟测试。

候选窗的 Qt 回归测试位于 `tests/test_candidate_window.py`，覆盖候选从七项减少到两项、
缓冲行出现/消失、窗口隐藏后重开、不同字体字号、DPI 缩放和实际背景绘制。

默认路由优先级如下：

```text
控制/符号/宏字典（包括多笔画前缀） -> Plover
英文和未接管的 stroke             -> Plover
中文模式下的 `=YAW-CAND:` outline -> 原生候选后端
中文模式下的其他普通 stroke       -> Plover
```

这意味着 Abby 左手修饰键字典、Ctrl/Alt/Shift/Win 组合键、上下左右、Home/End、功能键、
宏和英文自动空格不需要迁移到 Rime。原生候选后端只接管标记过的中文 outline，普通
Plover 字典仍按原顺序处理。旧的 JSON-lines sidecar、固定版本 librime 运行时和 Windows
ctypes 绑定仍放在 `plover_yawei_tiger/` 下，但不会被默认路线调用；候选控制器、Qt 候选窗口
和亚伟 stroke 到混合编码的可重复转换工具也已经加入。

### 开发者安装

在包含 Plover 的 Python 环境中执行：

```text
python -m pip install -e .
```

然后在 Plover 中选择 `Yawei V3`，启用 `yawei-rime` 扩展。默认会从已加载的
`yw-native-candidates.json` 自动启用原生候选后端和候选框，不需要安装 Rime 或设置环境变量。
若要测试整句 Rime 路线，请在启动 Plover 前设置 `PLOVER_YAWEI_BACKEND=rime`；该路线使用项目
自带的隔离 librime 数据目录，不读取或修改小狼毫用户目录。
扩展默认处于英文/透明模式；`IUNE-IU` 进入中文无空格模式，`IU-IUNE` 回到英文模式。
这两个 chord 在后端活动时由扩展自身消费，不会再执行旧词库中的全局空格模式命令；因此中文
不会自动插入空格，但 Plover 明确输出的空格、标点和宏仍保留原语义。中文候选可通过候选窗口的数字键、
Enter、Escape、方向键和翻页键操作，也可以直接在亚伟键盘上按上表的 `XNE-*` 数字 chord；
Plover 原有英文、符号、宏和编辑能力继续保留。
中文候选默认启用“嵌入首选/顶屏”：候选组出现时，第一候选会立即写入当前应用，
但候选窗口仍保持打开；按数字键选择其他候选时，扩展会先精确删除已嵌入的第一候选，
再写入所选候选。输入下一组完整音节会确认上一组首选并开始新的候选组，因此连续输入
`BA-BA`、`XBA-XBA` 会依次得到“爸爸”“妈妈”，不会把第二组拼音留在无候选的长预编辑中。
如果需要保留完整长词条优先的旧行为，可设置环境变量 `PLOVER_YAWEI_EMBED_FIRST=0`。
候选字典中的 `=YAW-CAND:` 是扩展内部协议，扩展会把它从普通 Plover lookup 中过滤，
因此忘记切换中文模式时也不会把协议 JSON 原样输出。

### 中文行缓冲（实验功能）

原生候选后端现在提供可选的 token 化行缓冲，用来模拟亚伟/E 迅的“先在行内组织、再按边界
上屏”行为。默认仍保持旧的即时 native 输出；测试新路线时，在 `yawei_tiger.cfg` 的
`[line_buffer]` 中设置 `enabled = true`，或启动前设置 `PLOVER_YAWEI_LINE_BUFFER=1`。
行缓冲开启后，唯一候选和多候选的首选都会先放入插件维护的中文行内缓冲，绝不会立即写入
目标程序；候选窗口中的首选只是当前可修改的 token。继续输入后，如果形成更长的词/短语，
前一个 token 会被整词替换，直到确认键或外部 Plover 命令边界才一次性上屏。行缓冲显示的是
已暂存的中文文本和候选列表；未匹配的编码不会额外显示拼音或物理键名。
`commit_on_prefix_miss` 控制前缀失配时的边界行为：启用时先解析最长完整 token、提交当前行，
再把造成失配的 stroke 作为下一 token 重放一次；关闭时只定界，整行仍留在插件缓冲中。
无论哪种设置，失配 stroke 都不会吞掉或重复消费。`commit`/`force_commit` 提交整行，`force_unbind` 只结束当前
自动绑定而不提交整行，实际解绑键位待冲突检查后再填写到 `[bindings]`。
`flush_before_plover_command = true` 会在 Plover 自己的符号、宏、方向键或编辑命令执行前
先同步中文行缓冲；`show_preedit = true` 会在行缓冲仍有文字时保持候选窗口显示。行缓冲
中的单字符退格只修改一个中文 token，未提交文字不会提前向目标程序发送退格；Delete 等
目标侧编辑命令会先同步行缓冲再交给 Plover。对未完成的自动绑定前缀执行 `force_unbind`
不会丢弃前缀，该控制 stroke 会回到 Plover 路由。

Plover JSON 是当前候选后端的源文件；Rime YAML 只是兼容后端的生成文件。修改 JSON 后，
在仓库根目录运行：

```text
python tools/rime/sync_dictionary.py
```

提交前可运行 `python tools/rime/sync_dictionary.py --check` 检查兼容用 Rime 文件是否同步。

## 已知限制和后续计划

1. 候选排序已经支持可选的实际词/短语词频，但加权词库仍是实验构建，不直接覆盖默认发布词库。词频只用于多候选编码；唯一映射不需要词频。生成器支持 `--frequency-file`（`词语<TAB>次数`），并提供脚本把万象 `jichu.dict.yaml` 提取成只覆盖本项目词库的频率表；同权重保持原顺序，缺少权重的词也不会被猜测排序。`tools/compare_candidate_frequency.py` 可生成中文对比报告，展示覆盖率、首选变化及具体编码的前后顺序，候选增删与仅排序变化分开统计。详见 [原生候选协议](docs/native-candidate-protocol.md#review-before-activation)。
2. 自动绑定/强制解绑键位仍是开发阶段绑定，最终 chord 需要和英文 Lapwing、符号表及编辑功能统一检查。
3. Rime 整句和本地 LLM 重排是可选实验，不替换默认的确定性 native 路线。
4. `plover-multi-candidate` 已有独立打包项目，但尚未作为单独插件正式发布。
5. E 迅 adapter 目前是参考理论和自动化接口，不代表已经支持 E 迅硬件。

可选词频表已覆盖 Plover 5 的完整启动、退出后重启和恢复正式词库流程。最小人工验收
见 [测试集第 12 节](TEST_PLAN.md#12-可选词频词库验收)：`A-BA` 在实验表中应显示
“阿爸、阿坝、阿巴”，可以明确区分原始排序与词频排序。

推荐顺序是：先稳定亚伟硬件和候选窗，再用真实词频完善候选排序和词库，最后评估本地 LLM 整句重排。

## 输入方式

### 拼音码

每个音节首先使用亚伟键位输入拼音。词库中的 `AO`、`ZIE`、`GINEO` 等大写字母组合是亚伟的音节 chord，不是要在普通键盘上逐个输入的字母。原生候选后端直接按完整 outline 查找候选，不把候选字符串交给 Rime 重新编码。

Plover 记法中：

- `-` 分隔同一个 chord 的左右手，例如 `AO-GINEO`；
- `/` 表示下一个 chord，例如 `AO-GINEO/XGNEO`；
- 一个词可以由多个音节 chord 组成。

亚伟的对称拼音叠音 chord 也会保留两个音节。例如 `BA-BA` 是一个 chord，含义是重复的
`ba-ba`；原生候选后端按两个物理 stroke 的完整 outline 查找，不会把它误缩成一个 `ba`。
保留的旧 Rime 代码会把它编码为 `ba'ba`，但当前默认路线不会经过这段代码。对称虎码辅码仍按一个形码处理，不会被错误拆成两个音节。

### 虎码辅码

仅靠拼音会产生大量同音候选，因此本方案从虎码取一个或两个字形码作为辅码。
单字继续使用现有的“拼音 + 右手虎码 chord”编码。例如虎码字母 `j` 对应右手
`-GINEO`，某个字的编码可能是 `AO-GINEO`。这部分是已有的单字 JSON 词条，暂不改变。

词和短语则使用候选筛选路线：词的基础 outline 只输入拼音音节，候选出现后再输入独立
辅码 stroke。扩展运行时从 `yawei_tiger_aux.txt` 读取每个汉字的虎码规则，根据左手首字、
右手末字或双手同时输入的辅码动态缩小候选，不再要求为每个词预先写一条带辅码后缀的
Plover outline。

这 26 个辅码 chord 使用独立的按键空间。拼音负责“读什么”，辅码负责“长什么”，两套编码在 Plover 中可以自然衔接和切分，常用词通常只需一位辅码，重码时再追加第二位。

26 个虎码字母到亚伟 chord 的映射如下，原始表见 `tools/theory_map/fu_to_virtual_keys.txt`：

| 虎码 | 亚伟 chord | 虎码 | 亚伟 chord | 虎码 | 亚伟 chord |
|:---:|:---|:---:|:---|:---:|:---|
| q | XGINEO / -XGINEO | w | WNEO / -WNEO | e | XNEO / -XNEO |
| r | XBZNEO / -XBZNEO | t | BDNEO / -BDNEO | y | WINEO / -WINEO |
| u | UNEO / -UNEO | i | INEO / -INEO | o | NEO / -NEO |
| p | BGNEO / -BGNEO | a | NEAO / -NEAO | s | XZNEO / -XZNEO |
| d | DNEO / -DNEO | f | XBUNEO / -XBUNEO | g | GNEO / -GNEO |
| h | XGNEO / -XGNEO | j | GINEO / -GINEO | k | XBGNEO / -XBGNEO |
| l | XDNEO / -XDNEO | z | ZNEO / -ZNEO | x | XINEO / -XINEO |
| c | BZNEO / -BZNEO | v | IUNEO / -IUNEO | b | BNEO / -BNEO |
| n | XBDNEO / -XBDNEO | m | XBNEO / -XBNEO |  |  |

### 空格和分词

英文可以使用 Plover 默认的按词空格。启用扩展后，扩展默认保持英文/透明路由；`IUNE-IU`
进入中文无自动空格模式，`IU-IUNE` 回到英文路由。模式切换由扩展消费，不会触发旧词库的
全局 `set_space`；Plover 明确要求的空格、标点和宏仍按原映射执行。
中文词库本身以词和短语为单位组织，配合候选选择或辅码后不需要在每个汉字之间手动敲空格。
也可以调用 `set_mode_strokes()` 换成自己的切换键。

这条“中文词条之间不自动加空格、显式空格仍有效”的规则属于中文原始理论/Yawei 路由层，
不是多重候选插件的通用行为。未来拆分组件时，模式键和无自动空格策略应随中文理论迁移；
候选插件只提供可复用的候选、筛选和行缓冲机制。详见
[组件归属与拆分边界](docs/component-ownership.md)。

## 为什么要重做

亚伟三代设备本身并不简单，真正让人难受的是配套软件：在较新的 Windows（尤其 Windows 11）上经常遇到兼容性问题，键盘也通常只能在厂商专用软件里工作，脱离它就无法正常向系统输入。更令人失望的是，这套软件给人的感觉像停留在二十年前，长期几乎没有实质性改进，界面、兼容性和工作流都没有跟上现代系统。

本项目的目标就是把硬件读取、中文词库和 Plover 的开放生态接起来，让亚伟键盘不再被锁死在一套难以维护的专用软件中；后续也可以用同一套理论兼容其他能够提供兼容键位的速录设备。

## 中文候选路线

### 纯 Plover 候选后端

Plover 的英文工作流建立在一个重要前提上：一个 chord 只能对应一个翻译。英文词库可以通过整理词典来满足这个前提，但中文存在大量同音字和同音词。当前方案只能不断追加虎码辅码，尽量把每个字词扩展成唯一编码；即使重码比例只有 10%～20%，在 Plover 中也会变成必须额外记忆和击打的辅码，输入体验会明显变差。

Rime 候选框和选择功能曾做成原型，但当前已关闭该路线，避免引入另一套词库格式和编码规则。本项目现在只走纯 Plover 插件路线：特殊字符串仍让每个 outline 对应一个 JSON 字符串值，扩展在运行时解析候选、维护输入状态并显示候选窗。英文、符号、宏、编辑键和方向键继续交给 Plover。

当前第一版已完成特殊值协议、候选索引、行缓冲显示、完整 outline 匹配、最长词边界、候选数字选择、左右手首末字筛选、同时双手筛选、连续辅码、首选嵌入/顶屏和候选上屏后的退格处理。迁移器从 `base.json` 生成了 36,606 个多候选组。26 个保留键位和字符虎码规则现在都由独立用户文件控制，改动后重启 Plover 即可生效。

共享候选核心另有一套基于 E 迅手册的参考理论 adapter，记录了每手四排 `5/5/2/1` 的物理布局，并覆盖声韵码、9 个特殊音节码、30 个简码、声调筛选和行缓冲提交。它是自动化软件适配，不是 E 迅设备驱动或 USB/HID 支持；尚未完成设备报告到 Plover stroke 的映射，也没有 E 迅真机验证。详见 [E 迅参考 adapter](docs/exun-reference-adapter.md)。

下一阶段是用真实键位配置做亚伟硬件冒烟测试，再用可复现的词频实验评估候选排序。默认发布词库仍保留源词条顺序；词频只通过显式的实验构建启用，不能把任一实验数据集直接视为最终排序。

### 后续：使用本地 LLM 做整句消歧

候选框解决的是“当前字词选哪个”，但中文整句还可以利用更大的上下文。随着本地小型 LLM 逐渐成熟，可以参考虎爪等方案，在输入法中加入本地模型，对原生候选进行整句重排或直接做句子级消歧。

LLM 不应一开始就替代确定性的编码和词库，而应放在候选流水线的后端：

- 纯 Plover 候选层先根据编码产生有限候选；
- 本地模型结合已经输入的句子，对候选进行重排或提出整句结果；
- 用户仍可查看候选并手动选择；
- 模型不可用、超时或置信度不足时，立即回退到词库原始顺序。

实现时优先考虑量化的小模型和本地运行，明确控制内存占用、首字延迟、每句延迟以及用户数据是否离开本机。需要建立可重复的测试集，分别评估单字、词语、长句、专有名词和技术文本，避免“看起来更聪明”却破坏确定性输入。

### 推荐实施顺序

1. 已完成 Yawei 硬件驱动和当前 Plover 词库的稳定性测试。
2. 已完成纯 Plover 特殊值协议、候选索引、候选框、选择键和中英文模式切换。
3. Rime 整句后端已接入为显式可选路线，默认仍使用 native。
4. 下一步：确认 26 个保留键的物理映射，用真实亚伟输入记录重码、选择次数和延迟。
5. 再调整候选排序，最后加入可选的本地 LLM 重排，并保留无 LLM 的完整工作模式。
