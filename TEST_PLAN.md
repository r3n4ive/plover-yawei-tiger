# 亚伟 Tiger + Plover + Rime 测试方案

本文用于验证第三代亚伟键盘、Plover Yawei Tiger 方案和隔离 librime 后端的实际使用效果。
测试时请按顺序执行；前一阶段失败时，先记录问题，不要跳过基础环境检查。

## 1. 测试准备

### 软件

- Windows 11
- Plover 4.0.3
- 已安装本项目插件
- 已连接第三代亚伟速录机

在 Plover 中确认：

1. System 选择 `yawei-tiger`。
2. Machine 选择 `Yawei V3`。
3. Extension 启用 `yawei-rime`。
4. 设置用户环境变量 `PLOVER_YAWEI_RIME_ENABLE=1`。
5. 完全退出并重新启动 Plover。

首次启动中文后端时，会下载固定版 librime 并创建独立数据目录：

```text
%LOCALAPPDATA%\Plover\yawei-rime
```

确认该目录中出现 `runtime\librime-1.17.0\rime.dll`、
`runtime\librime-1.17.0\rime_deployer.exe` 和 `data\shared\build`。

## 2. 硬件输入测试

### 2.1 设备连接

1. 不启动 Plover，打开记事本，按一次亚伟键盘任意组合。
2. 关闭记事本，启动 Plover，打开 Plover 的 Paper/Output 观察窗口。
3. 选择 `Yawei V3` 后按同一组合。

预期：Plover 能收到 stroke；记事本不会直接收到普通键盘字符。若 Plover 无 stroke，记录设备管理器中的 HID 状态和 Plover 日志。

### 2.2 键位方向

依次测试以下组合，记录 Plover 显示的 canonical stroke：

```text
左手单键：A- N- I- G- D- O- E- U- W- Z- B- X-
右手单键：-A -N -I -G -D -O -E -U -W -Z -B -X
左右组合：AO、GI、B-B、GI-GI、BX
```

预期：左右手不会镜像、错位或变成普通键盘字符；同一组合重复按下时显示相同 stroke。

## 3. Plover 英文和编辑回归

先保持英文模式，测试原有 Plover 功能不被 Rime 影响：

| 项目 | 操作 | 预期 |
| --- | --- | --- |
| 英文单词 | 输入 5 个常用英文词 | 每个词正常输出，词间自动空格 |
| 标点 | 输入句号、逗号、问号 | 标点正确，空格规则不异常 |
| 符号 | 测试已有符号字典 | 符号仍由 Plover 输出 |
| 修饰键 | 测试 Ctrl/Alt/Shift/Win 组合 | 组合键正常执行 |
| 编辑键 | 测试上下左右、Home、End、Backspace | 光标操作正常 |
| 宏 | 测试一个已有宏 | 宏仍然执行 |

记录是否出现中文模式残留、额外空格、重复输出或按键吞失。

## 4. 中文模式切换

使用默认切换 stroke：

```text
IUNE-IU  -> 进入中文模式
IU-IUNE  -> 回到英文模式
```

测试步骤：

1. 输入一个英文词，确认正常输出。
2. 按 `IUNE-IU`。
3. 输入 `AO`、`GI` 等中文编码 stroke。
4. 按 `IU-IUNE`。
5. 再输入英文词。

预期：切换 stroke 本身不会产生多余文字；中文模式下编码交给 Rime，英文模式下仍交给 Plover。

## 5. 中文候选测试

### 5.1 候选生成

在中文模式输入下列编码，记录 preedit、候选数量和第一候选：

```text
AO
GI
AO-GI
AO-GI/AO
```

预期：候选窗口出现；窗口中的候选文字不重复；输入相同 stroke 时结果稳定。

### 5.2 候选选择

对出现多个候选的编码执行：

1. 选择第 1 个候选。
2. 重新输入同一编码，选择第 2 个候选。
3. 输入编码后执行取消。
4. 输入编码后执行翻页，再选择候选。

记录：

- 选择后的文字是否只输出一次；
- 候选窗口是否关闭；
- 取消后是否清空 preedit；
- 翻页后候选是否变化；
- 选择后下一次输入是否从干净状态开始。

> 注意：候选窗口的数字键、Enter、Escape、方向键和翻页键属于候选控制路径。若窗口没有接收物理键盘事件，记录“候选显示正常、候选选择不可用”，不要把它误判成词库错误；这说明需要为亚伟键位配置候选控制 stroke。

### 5.3 中文空格

连续输入两个中文词，不在词间手动按空格。

预期：中文输出不出现英文式的词间空格；中文提交由 Rime 负责。切回英文后，英文词间自动空格恢复。

## 6. 字典同步测试

在仓库根目录运行：

```powershell
"C:\Program Files\Open Steno Project\Plover 4.0.3\data\python.exe" tools/rime/sync_dictionary.py --check
```

预期输出：

```text
Rime dictionary is up to date (... entries)
```

如果修改了 Plover JSON 字典，先运行：

```powershell
"C:\Program Files\Open Steno Project\Plover 4.0.3\data\python.exe" tools/rime/sync_dictionary.py
```

然后重新启动 Plover，并重复中文候选测试。

## 7. 故障记录模板

每个问题单独记录一行，尽量不要只写“不能用”：

| 时间 | 模式 | 原始按键/Stroke | 预期 | 实际 | 是否可复现 | 日志/截图 |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

故障报告至少包含：

- Plover 版本和插件 commit；
- 当前中文/英文模式；
- 亚伟原始按键顺序；
- Plover 显示的 canonical stroke；
- 是否出现候选窗口；
- 实际输出文本；
- 是否重启后仍可复现。

## 8. 测试结论

完成后按以下结论分类：

- `通过`：符合预期，可进入日常使用。
- `可用但需优化`：主流程可用，但候选选择、延迟或词库排序存在问题。
- `阻塞`：硬件无法读取、中文模式无法切换、Rime 初始化失败或英文功能回归。

优先修复顺序：硬件读取 -> 模式切换 -> 中文提交不重复 -> 候选选择 -> 候选排序和词库覆盖率。
