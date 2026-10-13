# 组件归属与两个项目的边界

2026-10-13 按用户确认拆成两个项目，亚伟硬件留在中文 theory。通用代码已迁出中文源码树，中文包通过 plover-multi-candidate>=0.1.0,<0.2 依赖它。

| 项目 | 本机目录 | 维护内容 |
| --- | --- | --- |
| [plover-yawei-tiger](https://github.com/r3n4ive/plover-yawei-tiger) | repo-sync | 中文 theory、词库/生成工具、拼音与虎码、中文策略、HID machine、模式路由 |
| [plover-multi-candidate](https://github.com/r3n4ive/plover-multi-candidate) | plover-multi-candidate | 通用候选协议、索引、组合状态机、辅筛接口、行缓冲、候选窗/设置 |

## 中文方案的修改入口

- plover_yawei_tiger/system.py：逻辑键名、键位序、普通键盘映射和默认词典。
- plover_yawei_tiger/machine.py：第三代亚伟 HID 报告及 Plover machine。HID 依赖仅属于这里。
- plover_yawei_tiger/dictionaries/：中文 JSON 词库、功能词典和三模式标记词典。
- tools/：中文词库生成、拼音/虎码转换、词频与冲突分析。
- plover_yawei_tiger/theory_map/：默认拼音、辅码 chord 与虎码字符表。
- plover_yawei_tiger/tiger_filter.py：首末字/连续虎码筛选。通用项目只规定筛选接口。
- plover_yawei_tiger/yawei_tiger.cfg：包内默认设置；运行时优先读取用户文件。
- plover_yawei_tiger/extension.py：中文模式、即时/行缓冲/外挂模式、中文自动空格策略和控制路由。
- plover_yawei_tiger/native_candidates.py：中文候选 marker 与通用状态机的适配层。

中文的“词间不自动加空格”由本项目负责。显式空格、英文、符号与键盘宏仍交给 Plover。可选 Rime 实验和外挂拼音也留在本项目，默认仍是原生 JSON 候选路线。

## 通用候选项目

独立项目拥有 CandidateState、CandidateBackend、CandidateIndex、CandidateCompositionBackend、CandidateFilter、LineBuffer/TokenRecord、CandidateController、候选窗和配置保存/设置工具。它不导入中文 theory，也不规定虎码、声调、中文空格或机器协议。

独立 wheel 只包含 plover_multi_candidate。E 迅手册参考 adapter 移到它的 examples/exun，仅用于软件测试，不安装到候选核心。测试与说明也随对应组件迁移。核心 Git 历史通过 subtree 提取保留；不使用子模块，今后只在独立仓库修改核心。

## 安装与兼容

开发安装顺序为候选包、中文包；也可把两个本地路径在同一条 pip 命令中安装。两个项目还未发布到 PyPI，因此不要只依赖在线安装来解析候选包。

亚伟继续使用 Yawei V3 machine、yawei-tiger system 和历史 yawei-rime extension。=YAW-CAND: marker、用户 yawei_tiger.cfg、辅码文件、词频表和当前开发按键保留。亚伟适配层调用独立核心，不额外启用 multi-candidate。旧 candidate、line_buffer、rime_protocol.CandidateState 导入路径继续作为薄兼容层。

独立候选项目单独使用时启用 multi-candidate，默认 marker 为 =PLOVER-CAND:，配置为 multi_candidate.cfg。同一个 marker 不应由两个扩展同时接管。

## 验证与后续

分别执行两个仓库的 python -m pytest -q，并构建/检查 wheel 和源码包。候选仓库可在无中文包的环境中验证；中文仓库测试依赖安装后的候选包。迁移人工检查仅需重启 Plover，确认亚伟候选、行缓冲提交和设置菜单可用，无需重复全部词频实验。

本次仅拆项目。PyPI/Plugin Manager 发布、最终控制键位和中文 theory 的具体调整仍待后续安排。
