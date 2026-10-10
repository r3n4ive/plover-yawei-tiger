# 亚伟 Tiger 原生候选路线：行缓冲与自动绑定任务书

状态：第一阶段已实现，待真实硬件验收  
日期：2026-10-06  
适用项目：`plover-yawei-tiger`  纯 Plover native candidate backend

## 1. 任务目标

在现有原生 Plover 候选后端上增加中文行缓冲和自动绑定，使中文速录的行为更接近亚伟、E 迅的实际使用方式：

- 输入过程先保留在插件自己的行缓冲中，不让跟打软件把临时转译误记成已经上屏的内容。
- 当前 stroke 既可能是一个完整词，又可能是更长 outline 的前缀时，先等待后续 stroke，支持长词。
- 后续 stroke 无法继续当前前缀时，确定最长的有效匹配，并把造成失配的 stroke 重新处理，避免吞键。
- 支持候选框、选重、强制解绑和显式上屏，同时保留 Plover 的英文、符号、宏、方向键和编辑功能。
- 中文模式下的删除、退格、撤销和选重不依赖 Plover 不可见的历史，避免行缓冲与 Plover 的回删记录不一致。

本任务只实现 native 路线的行缓冲和绑定状态机。Rime/librime 仍作为显式可选路线保留，但不在本任务中改造；声调拼音、Rime 整句模型和外挂输出模式另立任务。

## 2. 当前基线与约束

1. Plover JSON 仍遵守“一条 outline 对应一个字符串值”。多候选通过 `=YAW-CAND:` 特殊字符串协议表达，由插件运行时解析。
2. 原生候选后端默认启用；普通 Plover 字典、英文自动空格、符号和宏仍由 Plover 处理。
3. 原有候选窗口和候选数字选择逻辑继续使用。候选唯一时可以直接嵌入首选，候选不唯一时显示候选框。
4. 当前实现基线为已有测试全部通过（当前记录：108 项）。实现过程中不能用大范围重写覆盖工作树中已有的用户修改。
5. 亚伟硬件输入已经能转换为 canonical stroke；本任务处理的是 stroke 之后的词典匹配、候选和输出边界。

## 3. 术语

### 3.1 基本单位

- **stroke**：一次并击产生的 canonical chord，例如 `BA`、`MA`。
- **outline**：按顺序组成一个词或短语的 stroke 序列，例如 `BA/MA`。
- **token**：行缓冲中已经识别出的一个中文输入单元。token 可以是一个字、一个词或一个候选短语。
- **candidate set**：同一 outline 对应的候选列表。
- **preedit**：当前仍可改变的显示内容，包括未确定 token 和候选状态。
- **line buffer**：插件维护的整行中文输入状态。它不是目标应用已经收到的最终文本。

### 3.2 绑定术语

- **自动绑定**：当前输入同时满足“完整 outline”和“更长 outline 的前缀”时，暂不结束当前 token，等待后续 stroke 决定使用短词还是长词。
- **最长精确匹配**：在已经输入的 stroke 序列中，长度最长且确实存在于词典中的完整 outline。
- **前缀失配**：当前序列不再是任何 outline 的前缀，但其中可能存在一个较短的完整 outline。
- **强制解绑（`force_unbind`）**：结束当前自动绑定，建立 token 边界；默认不提交整行。
- **提交（`commit` / `force_commit`）**：确认当前候选并将行缓冲提交给目标程序。提交和解绑是两个不同动作。

## 4. 用户可见行为

### 4.1 普通输入

1. 第一个 stroke 到来后进入收集状态。
2. 如果当前序列只是前缀，继续等待。
3. 如果当前序列是完整 outline，同时也是更长 outline 的前缀，进入自动绑定等待态；短词不能立即破坏长词匹配。
4. 如果当前序列是完整 outline且不再是任何更长 outline 的前缀，按现有 native 候选逻辑处理：唯一候选可嵌入首选，多候选显示候选窗口。
5. 已确定 token 可以继续留在行缓冲中，直到显式提交或满足自动提交条件。

### 4.2 前缀失配与 stroke 重放

当下一 stroke 使当前序列不再是任何词典 outline 的前缀时：

1. 找到当前输入中最长的完整 outline。
2. 解析当前最长完整匹配并建立 token 边界。`commit_on_prefix_miss = true` 时，前缀失配
   同时是一个自动提交边界：先把当前行缓冲发送到目标程序，再处理新 stroke；设为 `false`
   时只定界，整行仍由 `commit`/`force_commit` 或 Plover 外部命令边界提交。
3. 将造成失配的 stroke 原样重新送入状态机，不能丢弃、合并或重复输出。
4. 如果不存在任何完整匹配，则清理这次无效收集，并把 stroke 回退给 Plover 正常路由。

这是解决“输入一个词后紧接下一个词会吞掉第一个 stroke”以及“长词候选跳着匹配”的核心规则。

### 4.3 强制解绑

`force_unbind` 是独立的中文控制动作：

- 结束当前自动绑定并建立 token 边界；
- 下一 stroke 必须开启新的 outline；
- 默认不提交整行，不改变当前已选择的候选；
- 不等同于 `commit`，也不等同于 `force_commit`；
- 如果当前没有待绑定 token，则不应产生空格、删除或其他副作用。

真实默认键位暂不在本任务中定死。候选方案为亚伟兼容性较好的 `WE`，或语义更接近“截断后续捆绑”的 `BR`/物理等价键；实现前必须完成与现有中文音节、Lapwing、Emily、Abby 和符号映射的冲突检查。

### 4.4 自动提交条件

行缓冲可以在以下条件下提交：

1. 用户执行 `commit` 或 `force_commit`。
2. 中文模式切换为英文模式。
3. Plover 自己拥有的符号、宏、方向键或系统快捷键即将执行，且该命令不属于中文候选控制；先处理中文行缓冲，再把命令交给 Plover。
4. 关闭扩展、切换机器或其他会丢失输入状态的生命周期事件。

前缀失配是否自动提交由 `commit_on_prefix_miss` 控制。启用时它与显式 `commit` 一样提交当前
行后重放失配 stroke；关闭时只结束当前 token，不改变整行的可编辑状态。

具体哪些 punctuation/Enter/Space 作为自动提交触发器，先复用现有 Plover 路由和配置，不在本任务中重新定义一套符号表。

## 5. 行缓冲数据模型

不能只保存一个待输出字符串。每个 token 至少记录：

```text
TokenRecord:
    text                 # 当前显示文本
    source_outline       # 产生它的完整 outline
    strokes              # 该 token 实际消耗的 stroke 序列
    candidates            # 候选列表及候选元数据
    selected_index        # 当前候选；未选择时为空
    is_bounded            # 是否已经通过自动/强制解绑确定边界
    is_committed           # 是否已经发送给目标程序
```

行缓冲至少保存：

```text
LineBuffer:
    tokens                # 有序 TokenRecord 列表
    pending_strokes       # 当前尚未定界的 stroke 序列
    preedit               # 给候选窗口显示的当前可变文本
    mode                  # idle / collecting / candidate / waiting_binding
    committed_text        # 已发送文本的可追踪记录
```

目标是让插件可以按 token 精确回删、替换候选、撤销最近一次中文操作，而不依赖 Plover 是否还记得某次输出的字符数。

## 6. 状态机设计

建议先实现下面的显式状态，而不是在 `consume()` 中加入更多隐式分支：

| 状态 | 含义 | 主要转移 |
| --- | --- | --- |
| `IDLE` | 没有未处理 stroke | 收到 stroke 后进入 `COLLECTING` |
| `COLLECTING` | 正在收集一个可能的 outline | 继续前缀、命中完整 outline、或前缀失配 |
| `WAITING_BINDING` | 当前既是完整 outline又是更长 outline前缀 | 下一 stroke 延长、失配解析、`force_unbind` |
| `CANDIDATE` | 当前 token 有候选或候选窗口 | 选重、提交、取消、继续输入 |
| `BOUNDED` | 当前 token 已结束但仍在行缓冲 | 开始下一个 token或整行提交 |
| `COMMITTING` | 正在把行缓冲发送到目标程序 | 完成后回到 `IDLE` |

核心转移伪代码：

```text
on_stroke(stroke):
    if is_force_unbind(stroke):
        bound_current_token_without_flushing_line()
        return CONSUMED

    append stroke to pending_strokes

    if trie.has_prefix(pending_strokes):
        if trie.has_exact(pending_strokes) and trie.has_longer_entry(pending_strokes):
            state = WAITING_BINDING
        elif trie.has_exact(pending_strokes):
            resolve_exact_match()
        else:
            state = COLLECTING
        return CONSUMED

    match = longest_exact_prefix(pending_strokes)
    if match exists:
        resolve(match)
        clear matched strokes
        if commit_on_prefix_miss:
            commit_line_buffer()
        replay current stroke once
        return CONSUMED

    clear invalid pending sequence
    return PASS_TO_PLOVER
```

实际代码需要用返回值或事件对象区分 `CONSUMED`、`PASS_TO_PLOVER` 和 `REPLAY`，禁止通过递归调用产生重复消费。

## 7. 前缀索引与匹配规则

1. 启动时从 native 候选词典建立 exact index 和 prefix trie/set。
2. trie 的节点保存“是否完整 outline”和“是否还有更长后继”，避免每次 stroke 扫描全部词典。
3. 候选匹配以完整 stroke 数为边界；不能把 `BA/BA/BA` 因为字符串前缀关系排在 `BA/BA` 的完整匹配之前。
4. 短词和长词同时存在时，长词只有在其所有 stroke 都实际输入后才可命中。
5. 候选排序先保持现有 native 规则；本任务只修正 outline 边界和前缀关系，不重新设计词频排序。
6. 对 `baba`、`通宵/通晓/同校` 等既有回归案例，候选必须按实际音节/outline 对齐，不能跨 token 跳着匹配。

## 8. 候选窗口与行缓冲的关系

候选窗口显示三部分：

1. 已确定的行缓冲文本；
2. 当前正在收集的 preedit/token；
3. 当前 token 的候选列表和选择状态。

行为要求：

- 行缓冲开启时，候选唯一或多候选的首选都只进入插件维护的行内 token，不会写入目标程序；
  关闭行缓冲时才沿用即时模式的嵌入首选行为；
- 候选不唯一时显示候选窗口，数字选重仍使用现有配置；
- 选择候选只替换当前 token，不得重排之前的 token；
- `Esc` 继续作为候选窗口取消/关闭动作，不能产生重复文本；具体取消后是否回到未选择状态，以现有候选测试为准；
- `commit`/`force_commit` 才是将整行送入目标程序的确认动作。

## 9. 与 Plover 编辑、宏和符号的边界

行缓冲会改变“谁拥有最近输出”的事实，因此必须显式定义优先级：

### 9.1 中文行缓冲活动时

- 退格、删除、撤销和候选选择先由 native backend 处理；
- 能按 token 回退时，不调用 Plover 的字符级回删；
- 对于 `backspace_word`/`delete_word`，按 token 边界删除，不能简单按字符长度猜测；
- 如果插件没有可操作的中文状态，再把命令交还给 Plover。

### 9.2 Plover 自有功能即将执行时

符号、宏、方向键、功能键、组合键和普通英文 outline 不属于中文候选控制时：

1. 先提交或定界中文行缓冲，确保目标程序中的文本与插件状态一致；
2. 再让 Plover 执行它原有的 translation/macro；
3. 不重复调用 `_send_backspaces`，不把同一个删除动作同时记入两个历史。

必须覆盖 `DG` 撤销、单字退格、整词退格、Delete、Escape、方向键和已有宏的回归测试。

## 10. 配置设计

配置名称先按下列逻辑确定，实际文件格式沿用项目现有 `yawei_tiger.cfg`：

```ini
[line_buffer]
enabled = true
commit_on_prefix_miss = true
flush_before_plover_command = true
show_preedit = true

[bindings]
# 以下命令键位目前全部只是开发测试绑定；完成中文、英文、符号和编辑
# 功能的整体冲突分析后，再统一决定最终 chord。force_unbind 留空表示
# 暂不启用，待冲突检查后填写 canonical stroke。
force_unbind =
commit = XNA-G
force_commit = XNA-XW
```

要求：

- 所有键位可由用户覆盖；
- `force_unbind` 为空时不能误绑定一个随机 stroke；
- `force_unbind` 与 `commit`/`force_commit` 启动时检查冲突；
- 配置错误要记录日志并回退安全行为，不得让 Plover 启动失败；
- 改配置后按项目现有约定重启 Plover 生效，暂不做热加载。

## 11. 实现顺序与当前进度

### 阶段 A：状态机测试（已完成）

先不碰 Qt 和硬件，使用内存词典、假的输出回调和假的 Plover engine 验证：

- 完整词/长词前缀的等待；
- 前缀失配后的最长匹配；
- 导致失配的 stroke 只重放一次；
- `commit_on_prefix_miss` 开关；
- 强制解绑不提交整行；
- 短 outline 不被更长 outline 的字符串前缀抢走。

当前 native 后端测试结果：108 项通过。新增测试覆盖行缓冲启用/关闭、长 outline 等待、
前缀失配、stroke 重放、强制解绑和整行提交。

### 阶段 B：建立 prefix trie 和 token 化行缓冲（第一版已完成）

- 从现有 native candidate index 派生 exact/prefix 索引；
- 建立 `TokenRecord`/`LineBuffer` 数据结构；
- 将当前候选、嵌入首选、选重和提交逻辑接入 token，而不是只操作一个字符串；
- 保证旧的单字、词、候选数字选择测试继续通过。

第一版通过 `PLOVER_YAWEI_LINE_BUFFER=1` 或配置文件 `[line_buffer] enabled = true` 启用，
默认仍关闭，以便在真实亚伟设备上逐步验收。

### 阶段 C：接入控制命令（已完成单元测试，待硬件验收）

- 加入可配置 `force_unbind`；
- 统一 `commit`/`force_commit` 与候选窗口动作；
- 让中文状态下的退格、删除、撤销优先操作行缓冲；
- 让 Plover 符号、宏、方向键和英文 outline 在边界处安全交接。

`commit`、`force_commit`、`flush`、`force_unbind` 已加入 backend 接口；最终实际键位仍待
冲突检查后配置。

本轮补充：`flush_before_plover_command` 和 `show_preedit` 已接入配置与 backend；行缓冲下
的单字符退格现在只删一个 token 字符，未上屏 token 不会向目标程序发送退格；Delete 会先
同步未提交行缓冲再回退给目标应用。`force_unbind` 遇到未完成 prefix 时会保留 prefix 并
把控制 stroke 交回 Plover，不再静默丢键。

### 阶段 D：接入候选窗口（基础显示已完成，待真实窗口验收）

- 显示行缓冲、当前 preedit 和候选列表；
- 检查候选切换、Esc、数字选重、首选嵌入和提交后的状态清理；
- 验证不会把候选协议字符串泄漏到目标程序。

当前已完成基础显示规则：行缓冲有 preedit 时可通过 `show_preedit` 保持窗口可见；候选
唯一且无行缓冲时仍隐藏窗口。数字选重在行缓冲中只替换 token，直到 `commit`/`flush` 才
写入目标程序。

### 阶段 E：亚伟三代冒烟测试

在不启动亚伟厂商软件的情况下连接 YW-V-3，验证真实 stroke、自动绑定、强制解绑、行提交和 Plover 控制命令；最后再验证拔插和重连。

## 12. 验收测试集

使用最小测试词典：

```text
BA       -> 爸爸、巴巴
BA/MA    -> 爸爸妈妈
MA       -> 妈妈、麻麻
NI       -> 你
```

必须通过：

1. 输入 `BA`：如果它仍是 `BA/MA` 的前缀，进入等待绑定，不误提交长词，也不丢失 `BA`。
2. 输入 `BA/MA`：命中“爸爸妈妈”，候选与 stroke 数严格对应。
3. 输入 `BA` 后执行 `force_unbind`，再输入 `MA`：不得命中 `BA/MA`，应形成两个 token。
4. 输入 `BA` 后输入未知/无法继续的 stroke：先解析 `BA`，再重新处理该 stroke；该 stroke 不能吞掉或重复。
5. `commit_on_prefix_miss=true`：失配时提交行缓冲；设为 `false`：只定界，不自动提交整行。
6. 候选唯一时可隐藏候选窗口但仍保留可回退状态；候选不唯一时显示窗口并能用数字选择。
7. 连续输入“一心一意”这类短词组合时，最长词只在所有 stroke 到齐后命中；用户用 `force_unbind` 后仍能选择较短的两个词。
8. 中文行缓冲活动时执行退格、整词退格、Delete、撤销和 Esc，不重复输出、不多删、不把插件状态和目标文本弄成两套。
9. 中文行缓冲后执行 Plover 的符号、宏、方向键、功能键和英文 outline：中文先安全定界/提交，Plover 命令只执行一次。
10. 中文模式切回英文、Plover 重启、亚伟拔插重连后，不残留旧 token、候选或绑定状态。

## 13. 暂不解决的问题

以下内容不属于明天的实现范围：

- 把 Rime/librime 重新作为 native 路线的翻译核心；
- 带声调拼音的任意位置组合和 Rime 整句语言模型；
- 重新计算中文键位布局或更换虎码辅码；
- Lapwing/Emily/Abby 全量重排和新符号表设计；
- 最终 `force_unbind` 物理键位的拍板；
- 词频排序算法的大改。

## 14. 完成定义

任务完成必须同时满足：

1. 状态机、前缀 trie、行缓冲和控制命令有单元测试；
2. 原有测试基线不回归；
3. 人工测试集第 0、1、2、3、4、5、6、9、10 节通过；
4. 中文候选、英文 Plover 功能、符号/宏和亚伟真实硬件边界经过记录；
5. `force_unbind` 的默认键位、配置示例和行为写入 README/用户文档；
6. 日志能区分：普通 Plover 路由、中文行缓冲、前缀失配重放、候选提交和强制解绑。

实现过程中如果发现 Plover 内部 undo 栈与行缓冲无法安全同步，优先保留插件内 token 历史并明确命令边界，不通过猜测目标程序文本来“修正”状态。
