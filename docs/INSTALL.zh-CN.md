# Apple Silicon 安装与实机验收

目标为 macOS 27.0.1（26A434）。CI 的系统版本单独记录，不能代替此目标版本实测。
驱动使用传统 CUPS PPD/filter，系统负责 USB 传输，不含扫描功能。
安装不需要 Rosetta。未签 Developer ID、未公证；二进制采用本地 ad-hoc 签名。

## 从源码构建

需要 Apple Command Line Tools、CMake、Python 3；驱动运行时不依赖 Python、CMake 或 Homebrew 库。
源码及 JBIG 已在仓库中，构建脚本不下载依赖。

```sh
sh scripts/build-macos.sh
python3 scripts/package-macos.py
```

构建会测试核心、CUPS 输入、Apple PDF 转换、签名、架构和 PPD。
输出 `build-package/M1136-Mac-Driver-arm64.tar.gz`。

## 安装准备

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

## 实机验收（尚未完成）

1. 先打印一页 A4 黑白测试 PDF，确认真正出纸、方向、边距。
2. 测试灰阶、细线、小字，以及 Letter（使用匹配纸张）。
3. 测试两页、两份，确认份数及排序，不重复打印。
4. 测试取消、USB 拔插及打印机重启后的恢复。
5. 记录 `sw_vers`、构建提交、测试结果及 CUPS 错误；不要上传含私人文档的光栅。

```sh
lp -d HP_M1136_Native_C -o PageSize=A4 test.pdf
lpstat -p HP_M1136_Native_C
```

当前输出按页携带份数；逐份排序由上游 CUPS 排版处理，需实机验证。
仅支持 600dpi、A4/Letter、单面、1–99 份、最多 500 个输入页面。
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
