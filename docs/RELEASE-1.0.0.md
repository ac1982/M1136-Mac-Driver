# M1136 Mac Driver 1.0.0

HP LaserJet Professional M1136 MFP 的原生 Apple Silicon USB 打印驱动。

## 下载与安装

下载 `M1136-Mac-Driver-1.0.0-arm64.pkg`。发布包由 Pulse（89G3DBC6CS）签名，
经过 Apple 公证并装订票据。`SHA256SUMS` 提供最终摘要，源码归档提供对应 GPL 源码。
安装或升级步骤见仓库 README 和 `docs/INSTALL.zh-CN.md`；首次安装需要手动创建 USB 队列。

## 本版修复

- 使用 raster 每页 NumCopies，修复逐份打印将 3 份放大成 9 份的问题。
- 非阻塞输入输出和有限等待修复取消信号与阻塞 I/O 之间的竞态。
- 将打包绑定到已验证源码与二进制摘要，拒绝旧构建或构建后修改。
- 统一 1.0.0 版本元数据，并添加 PPD 一致性检查。

## 验证与限制

本机 Apple Silicon / macOS 27.0.1（26A434）安装 1.0.0 候选构建后，
三份 A4 校准页和一份 Word 文档均实际出纸，用户确认数量及效果正常。
正式附件由 Actions 从标签源码重新构建；软件测试、签名和公证结果见 Actions 与发布报告。

支持 600 dpi、A4/Letter、单面、1–99 份、最多 500 个输入 raster 页面。
不支持扫描、自动双面或驱动辅助的手动双面。
Letter 实物打印、多页逐份排序、取消后的设备恢复、USB 拔插与断电恢复仍待实测。
