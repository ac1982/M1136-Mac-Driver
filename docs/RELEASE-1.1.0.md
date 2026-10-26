# M1136 Mac Driver 1.1.0

HP LaserJet Professional M1136 MFP 的原生 Apple Silicon USB 打印驱动，新增手动双面。

## 下载与安装

下载 `M1136-Mac-Driver-1.1.0-arm64.pkg`。驱动与安装包由 Pulse（89G3DBC6CS）
使用 Developer ID 签名，经过 Apple 公证并装订票据。
`SHA256SUMS` 提供最终摘要，发布报告记录构建提交及公证结果，源码归档提供对应 GPL 源码。

双击安装包并按 macOS 提示授权。已有队列升级后刷新 PPD：

```sh
sudo lpadmin -p HP_M1136_Native_C -P /Library/Printers/M1136MacDriver/M1136.ppd
```

首次安装与回滚见仓库 `docs/INSTALL.zh-CN.md`。

## 新增功能

- 手动双面支持长边、短边装订；先打印奇数页，再按倒序打印偶数页，奇数页数自动补空白背面。
- 在打印窗口的打印机功能中选择 `Manual Duplex (1 copy; reload at H1)`，每次打印 1 份。
- 等待 H1 后，把整叠纸保持原方向和顺序、已打印面朝下放回进纸仓，按打印机复印键继续。
- 最多 200 页／100 张；压缩暂存上限 512 MiB，私有临时文件立即 unlink。
- 完整验证双面输入后才发送到打印机；新增回放取消、管道断开、暂存错误和容量边界测试。

操作步骤见 `docs/MANUAL-DUPLEX.zh-CN.md`。本机不具备自动双面硬件；扫描不在项目范围内。

## 验证与限制

本机 Apple Silicon / macOS 27.0.1（26A434）的已签名、公证 1.1.0 候选包，
通过 Word 打印四页 A4 长边双面，用户确认两张纸正反配对与方向正常，放回纸后按复印键继续。
正式附件由 GitHub Actions 从本标签干净源码重新构建，未逐包重新进行物理打印。

Release 和 ASan/UBSan 各 9 项测试，以及 18 种 Apple PDF → raster → XQX 管线检查通过；
具体发布构建结果见 Actions 与发布报告。
短边、奇数页、Letter、横向页面及设备取消、USB 拔插、断电后的恢复仍待真机验收。
CUPS 可能在打印机等待回放时显示已完成；清空电脑队列不能保证撤回机内缓存任务。
