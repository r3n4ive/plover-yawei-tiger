# plover-yawei-tiger

这是一个在 Plover 上使用中文的亚伟速录方案。中文输入不可避免会遇到同音字和多候选，本项目用“拼音码 + 虎码辅码”构建词库，把候选筛选也纳入速录击键中。

## 亚伟键盘支持

项目支持第三代亚伟 YW-V-3 硬件键盘。安装本项目和 `hidapi` 后，在 Plover 中将机器选择为 `Yawei V3`，即可直接读取亚伟键盘的 HID 报告；普通键盘模拟仍可选择 `Keyboard`。

## 安装和运行时路由

本项目正在把中文候选能力做成 Plover 插件，而不是要求用户修改 Plover 安装目录。安装开发包后，Plover 会注册以下组件：

- `Yawei V3` machine：读取第三代亚伟 HID 键盘；
- `yawei-tiger` system：当前拼音 + 虎码辅码键位系统；
- `yawei-rime` extension：为中文后端提供翻译前路由；
- 现有 Plover 字典：符号、宏、修饰键、方向键和英文仍由 Plover 处理。

在 Plover 的插件设置中启用 `yawei-rime` 后，扩展会在当前 engine 实例上安装一个可撤销的兼容钩子。它不会覆盖或改写 `Plover 4.0.3` 的安装文件；停用扩展后会恢复原始流程。没有配置中文后端时扩展是透明的，所有 stroke 都回退到 Plover。

要启用直接连接小狼毫 `rime.dll` 的候选后端，设置环境变量
`PLOVER_YAWEI_RIME_ENABLE=1` 后重启 Plover。扩展会自动查找
`%ProgramFiles%\Rime\weasel-*\rime.dll` 和 `%APPDATA%\Rime`；也可以用
`PLOVER_YAWEI_RIME_DLL`、`PLOVER_YAWEI_RIME_USER_DIR`、
`PLOVER_YAWEI_RIME_SCHEMA` 覆盖默认路径和 schema。找不到 DLL、用户目录或映射文件时，扩展会记录日志并保持 Plover 原有行为。

候选控制可由插件配置绑定到亚伟 chord。例如在扩展初始化代码中调用
`set_command_stroke("-A", "select", 0)`、`set_command_stroke("-O", "page_next")`
和 `set_command_stroke("-E", "commit")`。候选窗口中的数字 1-9、Enter、Escape、方向键和翻页键也会调用同一套 backend 命令；这些绑定只在中文模式生效。

### 运行测试

测试必须使用 Plover 自带的 Python 环境，因为 machine 和插件依赖 Plover 的运行时包：

```text
"C:\\Program Files\\Open Steno Project\\Plover 4.0.3\\data\\python.exe" -m pytest tests -q
```

测试不需要连接亚伟硬件；HID 报告和 Rime 通信均有模拟覆盖。真实设备仍建议在发布前做一次人工冒烟测试。

路由优先级如下：

```text
控制/符号/宏字典（包括多笔画前缀） -> Plover
英文和未接管的 stroke             -> Plover
中文模式下的普通编码 stroke       -> Rime 后端
```

这意味着 Abby 左手修饰键字典、Ctrl/Alt/Shift/Win 组合键、上下左右、Home/End、功能键、宏和英文自动空格不需要迁移到 Rime。后端接口、JSON-lines sidecar 协议和 Windows `librime` ctypes 绑定已放在 `plover_yawei_tiger/sidecar.py`、`plover_yawei_tiger/rime_protocol.py` 与 `plover_yawei_tiger/rime_backend.py`。当前绑定可以独立启动小狼毫的 `rime.dll`、创建指定 schema 的 session、读取候选并提交；候选控制器、Qt 候选窗口和亚伟 stroke 到混合编码的可重复转换工具也已经加入，最终配置向导和专用控制 chord 仍在开发中。

### 开发者安装

在包含 Plover 的 Python 环境中执行：

```text
python -m pip install -e .
```

然后在 Plover 中选择 `Yawei V3`，启用 `yawei-rime` 扩展。当前扩展默认处于英文/透明模式；Rime 中文模式和候选框完成后会加入专用切换 chord 与候选操作键。

## 输入方式

### 拼音码

每个音节首先使用亚伟键位输入拼音。词库中的 `AO`、`ZIE`、`GINEO` 等大写字母组合是亚伟的音节 chord，不是要在普通键盘上逐个输入的字母。

Plover 记法中：

- `-` 分隔同一个 chord 的左右手，例如 `AO-GINEO`；
- `/` 表示下一个 chord，例如 `AO-GINEO/XGNEO`；
- 一个词可以由多个音节 chord 组成。

### 虎码辅码

仅靠拼音会产生大量同音候选，因此本方案从虎码取一个或两个字形码作为辅码。生成词库时，先为汉字查找虎码，再把虎码字母替换成独立的亚伟 chord。例如虎码字母 `j` 被替换为 `GINEO`，所以某个字的拼音和第一位辅码可能组合成 `AO-GINEO`；需要第二位辅码时则继续使用 `/` 连接下一个 chord。

这 26 个辅码 chord 使用独立的按键空间。拼音负责“读什么”，辅码负责“长什么”，两套编码在 Plover 中可以自然衔接和切分，常用词通常只需一位辅码，重码时再追加第二位。

26 个虎码字母到亚伟 chord 的映射如下，原始表见 `tools/theory_map/fu_to_virtual_keys.txt`：

| 虎码 | 亚伟 chord | 虎码 | 亚伟 chord | 虎码 | 亚伟 chord |
|:---:|:---|:---:|:---|:---:|:---|
| q | XGINEO | w | WNEO | e | XNEO |
| r | XBZNEO | t | BDNEO | y | WINEO |
| u | UNEO | i | INEO | o | NEO |
| p | BGNEO | a | NEAO | s | XZNEO |
| d | DNEO | f | XBUNEO | g | GNEO |
| h | XGNEO | j | GINEO | k | XBGNEO |
| l | XDNEO | z | ZNEO | x | XINEO |
| c | BZNEO | v | IUNEO | b | BNEO |
| n | XBDNEO | m | XBNEO |  |  |

### 空格和分词

英文可以使用 Plover 默认的按词空格。启用 Rime 后，`IUNE-IU` 默认进入中文路由，`IU-IUNE` 默认回到英文路由；这两个 chord 同时保留原有的 Plover 空格模式命令。未启用 Rime 时，扩展不会拦截它们。中文词库本身以词和短语为单位组织，配合辅码后不需要在每个汉字之间手动敲空格。也可以调用 `set_mode_strokes()` 换成自己的切换键。

## 为什么要重做

亚伟三代设备本身并不简单，真正让人难受的是配套软件：在较新的 Windows（尤其 Windows 11）上经常遇到兼容性问题，键盘也通常只能在厂商专用软件里工作，脱离它就无法正常向系统输入。更令人失望的是，这套软件给人的感觉像停留在二十年前，长期几乎没有实质性改进，界面、兼容性和工作流都没有跟上现代系统。

本项目的目标就是把硬件读取、中文词库和 Plover 的开放生态接起来，让亚伟键盘不再被锁死在一套难以维护的专用软件中；后续也可以用同一套理论兼容其他能够提供兼容键位的速录设备。

## 后续开发计划

### 1. 引入候选框和 librime

Plover 的英文工作流建立在一个重要前提上：一个 chord 只能对应一个翻译。英文词库可以通过整理词典来满足这个前提，但中文存在大量同音字和同音词。当前方案只能不断追加虎码辅码，尽量把每个字词扩展成唯一编码；即使重码比例只有 10%～20%，在 Plover 中也会变成必须额外记忆和击打的辅码，输入体验会明显变差。

中文更适合保留重码，再通过候选框选择结果。因此计划引入 `librime`，复用成熟的中文编码、候选排序和词语上下文能力，不再重新实现一套中文输入引擎。

这里需要区分两个组件：`librime` 负责输入状态、候选列表和提交结果，但它本身不是 Windows 候选框界面。候选框和 Plover 的连接可以分成几个阶段：

1. 定义桥接协议：把 Yawei/Plover 的 canonical stroke 传给 Rime，返回 preedit、候选列表、分页信息和最终提交文本。
2. 先做旁路原型：Plover 继续负责硬件采集和英文翻译，中文模式把连续 stroke 转发给一个 librime sidecar 进程，验证候选逻辑和延迟。
3. 实现候选 UI：提供跟随光标的 Windows 候选框，支持数字键、方向键、翻页和取消；候选框不可用时仍能回退到当前 Plover 词典输出。
4. 再决定集成方式：可以做 Plover 插件内嵌，也可以做独立的 Windows 输入法/桥接程序。独立进程更容易隔离 librime 和 UI 崩溃，插件内嵌则更容易共享 Plover 的 stroke 状态。
5. 保留双模式：英文继续使用 Plover 的一对一词库和自动空格，中文交给候选引擎处理；两种模式之间应有明确、可记忆的切换键。

第一阶段的验收标准是：中文允许重码、有可见候选框、能稳定选择和提交，英文现有输入不受影响；在 librime 或候选 UI 异常时，Plover 仍可作为基本输入工具使用。

### 2. 使用本地 LLM 做整句消歧

候选框解决的是“当前字词选哪个”，但中文整句还可以利用更大的上下文。随着本地小型 LLM 逐渐成熟，可以参考虎爪等方案，在输入法中加入本地模型，对 Rime 产生的候选进行整句重排或直接做句子级消歧。

LLM 不应一开始就替代确定性的编码和词库，而应放在候选流水线的后端：

- Rime 先根据编码产生有限候选；
- 本地模型结合已经输入的句子，对候选进行重排或提出整句结果；
- 用户仍可查看候选并手动选择；
- 模型不可用、超时或置信度不足时，立即回退到 Rime 原始排序。

实现时优先考虑量化的小模型和本地运行，明确控制内存占用、首字延迟、每句延迟以及用户数据是否离开本机。需要建立可重复的测试集，分别评估单字、词语、长句、专有名词和技术文本，避免“看起来更聪明”却破坏确定性输入。

### 推荐实施顺序

1. 先完成 Yawei 硬件驱动和当前 Plover 词库的稳定性。
2. 定义 stroke 到候选引擎的桥接协议，做 librime sidecar 原型。
3. 完成中文候选框、选择键和中英文模式切换。
4. 统计真实输入中的重码、选择次数和延迟，调整词库与候选排序。
5. 最后加入可选的本地 LLM 重排，并保留无 LLM 的完整工作模式。
