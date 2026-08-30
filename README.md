# plover-yawei-tiger

在plover上使用中文的解决方案。
中文难以避免多候选，本项目提供了一种通过技巧构建词库来在plover上使用中文速录的方法。

## 亚伟键盘支持

项目现已支持第三代亚伟 YW-V-3 硬件键盘。安装本项目后，在 Plover 中将机器选择为 `Yawei V3` 即可直接读取亚伟键盘的 HID 报告；驱动依赖 `hidapi`，普通键盘模拟仍可使用 `Keyboard` 机器。
