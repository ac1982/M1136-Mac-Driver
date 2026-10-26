# Apple Silicon 安装与实机验收

目标为 macOS 27.0.1（26A434）。CI 的系统版本单独记录，不能代替此目标版本实测。
驱动使用传统 CUPS PPD/filter，系统负责 USB 传输，不含扫描功能。
安装不需要 Rosetta。默认开发构建采用 ad-hoc 签名；Pulse 发布构建使用 Developer ID 签名与 Apple 公证。

## 从源码构建

需要 Apple Command Line Tools、CMake、Python 3；驱动运行时不依赖 Python、CMake 或 Homebrew 库。
源码及 JBIG 已在仓库中，构建脚本不下载依赖。

```sh
sh scripts/build-macos.sh
python3 scripts/package-macos.py
```

构建会测试核心、CUPS 输入、Apple PDF 转换、签名、架构和 PPD。
输出 `build-package/M1136-Mac-Driver-arm64.tar.gz`。
打包时会核对源码和已测试、已签名二进制的摘要；更新源码后必须重新运行构建脚本。
本地未提交修改可以构建，包内 `BUILD.json` 会标记 `git_dirty: true`，不能当作纯净提交的构建。

## Pulse 签名发布包

在已配置 Pulse 团队签名钥匙串的 Mac 上：

```sh
sh scripts/build-macos.sh --developer-id
python3 scripts/package-signed-macos.py --notarize
```

二进制启用 hardened runtime 和可信时间戳，Team ID 为 `89G3DBC6CS`。
脚本显式使用既有钥匙串，不导出或复制私钥；默认公证 profile 为 `pulse-notary`。
只有 Apple 返回 Accepted、票据装订和 Gatekeeper 检查通过后，发布报告才标记装订成功。
失败后先根据 `M1136-Mac-Driver-release.json` 的 submission_id 查询状态，避免盲目重传。
可通过 `M1136_SIGNING_KEYCHAIN`、`M1136_NOTARY_PROFILE` 指定既有配置，
证书续期后通过 `M1136_APPLICATION_IDENTITY` 指定新证书指纹，仍强制核对 Pulse 团队和组织。

发布目录 `build-package/` 包含 `.pkg`、最终 `.pkg.sha256`、发布报告和对应源码归档。
请将 `M1136-Mac-Driver-source.tar.gz` 与二进制一起分发，以提供对应源码。
`.tar.gz` 开发安装包本身不能装订公证票据；对外安装优先使用已装订的 `.pkg`。

双击 `M1136-Mac-Driver-1.1.0-arm64.pkg` 安装。它仅安装或更新本项目的两个驱动文件，
不创建队列、不改变默认打印机、不自动打印；已有 `HP_M1136_Native_C` 队列会继续使用同一路径。
安装更新前请确保该队列没有正在打印的任务。
CUPS 保留独立的队列 PPD 副本；已有队列更新后，用以下命令刷新其版本和能力：

```sh
sudo lpadmin -p HP_M1136_Native_C -P /Library/Printers/M1136MacDriver/M1136.ppd
```
首次安装在 `lpinfo -v` 中核对设备 URI 后创建队列：

```sh
sudo lpadmin -p HP_M1136_Native_C -E -v 'usb://替换为实际设备URI' \
  -P /Library/Printers/M1136MacDriver/M1136.ppd \
  -D 'HP M1136 Native C' -o printer-is-shared=false
```

该 PKG 的收据标识为 `com.pulse.m1136.driver`。手动回滚删除文件后，可用
`sudo pkgutil --forget com.pulse.m1136.driver` 移除本项目的安装收据。

## 开发归档安装准备

解压安装包，阅读 `BUILD.json` 的提交和构建系统信息、检查安装脚本。
在安装包目录执行：

```sh
shasum -a 256 -c SHA256SUMS
/usr/sbin/lpinfo -v
```

从系统结果中找到实际连接的 HP M1136 的完整 `usb://...` URI，核对型号和序列号。
不要使用别人的序列号，也不要用网络 URI。摘要只检验包内一致性，不证明发布者身份。

确认设备与包后，在 Mac 本机明确执行管理员安装：

```sh
sudo sh install-macos.sh 'usb://这里替换为系统发现的完整设备URI'
```

脚本只创建 `/Library/Printers/M1136MacDriver` 和 `HP_M1136_Native_C` 队列；
目标目录或队列已有内容时拒绝覆盖。不会删除其他驱动、设置默认打印机或自动打印。
若创建队列失败，文件保留，按下方回滚，排查后重新安装。

## 实机验收范围

已完成本机 1.0.0 的三份 A4 校准页和一份 Word 文档测试，用户确认共四张且效果正常。以下项目可用于进一步验收：

1. 打印一页 A4 黑白测试 PDF，确认真正出纸、方向、边距。
2. 测试灰阶、细线、小字，以及 Letter（使用匹配纸张）。
3. 测试两页、两份，确认份数及排序，不重复打印。
4. 测试取消、USB 拔插及打印机重启后的恢复。
5. 记录 `sw_vers`、构建提交、测试结果及 CUPS 错误；不要上传含私人文档的光栅。

```sh
lp -d HP_M1136_Native_C -o PageSize=A4 test.pdf
lpstat -p HP_M1136_Native_C
```

当前输出按页携带份数；逐份排序由上游 CUPS 排版处理，需实机验证。
单面支持 600dpi、A4/Letter、1–99 份、最多 500 个输入页面。
1.1.0 起支持[手动双面](MANUAL-DUPLEX.zh-CN.md)，每次 1 份、最多 200 页。
拒绝压缩 CUPS raster 容器；Apple PDF 流程使用未压缩 raster，打印机端仍为 JBIG。

## 回滚

仅移除本项目队列及两个安装文件：

```sh
sudo lpadmin -x HP_M1136_Native_C
sudo rm /Library/Printers/M1136MacDriver/rastertom1136
sudo rm /Library/Printers/M1136MacDriver/M1136.ppd
sudo rmdir /Library/Printers/M1136MacDriver
```

队列尚未创建时，第一条可能报不存在；继续核对两个文件后删除。
