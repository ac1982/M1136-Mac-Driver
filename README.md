# M1136 Mac Driver 1.0.0

为 **HP LaserJet Professional M1136 MFP** 提供原生 Apple Silicon USB 打印支持。
无需 Rosetta，不增加网络打印服务。驱动使用系统 CUPS，业务代码为 C，压缩使用 JBIG-KIT 2.2。

**已在 Apple Silicon / macOS 27.0.1（26A434）连接 M1136 实机验证基本打印。**
本机 1.0.0 构建完成三份 A4 校准页和一份 Word 文档打印，用户确认张数、文字、灰阶及边距正常。
这不代表所有系统、设备恢复和纸型场景均已验证。

## 下载与安装

从 [Releases](https://github.com/ac1982/M1136-Mac-Driver/releases/latest) 下载
`M1136-Mac-Driver-1.0.0-arm64.pkg`。正式发布包由 **Pulse**（Team ID `89G3DBC6CS`）
进行 Developer ID 签名，经过 Apple 公证并装订票据；发布附件包含校验和、构建记录和对应源码。

1. 连接打印机并放入 A4 纸，双击 `.pkg`，按 macOS 提示授权安装。
2. 首次安装需要创建打印队列。运行 `/usr/sbin/lpinfo -v`，找到本机 M1136 的完整 `usb://...` URI，再执行：

   ```sh
   sudo lpadmin -p HP_M1136_Native_C -E -v 'usb://替换为本机实际设备URI' \
     -P /Library/Printers/M1136MacDriver/M1136.ppd \
     -D 'HP M1136 Native C' -o printer-is-shared=false
   ```

3. 在 Word、预览等应用的打印窗口选择 **HP M1136 Native C**。

安装包只安装或更新 `/Library/Printers/M1136MacDriver/` 下的驱动和 PPD，
不自动创建队列、不改变默认打印机、不自动打印。升级前请等待当前打印任务完成。
已有队列升级后刷新 CUPS 的 PPD 副本：

```sh
sudo lpadmin -p HP_M1136_Native_C -P /Library/Printers/M1136MacDriver/M1136.ppd
```

详细步骤、摘要验证和卸载见 [安装与回滚](docs/INSTALL.zh-CN.md)。

## 支持范围

| 项目 | 状态 |
|---|---|
| 平台 | 原生 ARM64；目标系统 macOS 27.0.1，CI 宿主版本另见发布记录 |
| 连接 | 系统 CUPS USB backend |
| 打印 | 600 dpi、黑白/灰阶、A4 和 Letter、单面 |
| 份数 | 1–99 份，使用每页 raster NumCopies，避免逐份打印重复乘份数 |
| 页数 | 每个任务最多 500 个输入 raster 页面 |
| 自动双面 | 不支持，双面输入会被拒绝 |
| 驱动辅助的手动双面 | 尚未实现“暂停、整叠回放、继续打印”流程 |
| 扫描 | 不在项目范围内 |

A4 基本打印和三份数量已实测；Letter 实物打印、多页逐份排序、取消后恢复、USB 拔插和断电恢复仍待验证。
PPD 设置 12pt 可打印边界，当前打印效果已获用户确认，但不是全设备范围的精密边距校准。

## 构建与测试

需要 Apple Silicon Mac、Xcode Command Line Tools、CMake 和 Python 3。
普通开发构建使用 ad-hoc 签名，不要求发布证书：

```sh
sh scripts/build-macos.sh
python3 scripts/package-macos.py
```

构建不下载压缩库，运行时仅直接依赖 macOS libcups 与 libSystem。
输出在 `build-package/`。打包要求源码和已验证二进制与构建记录一致；修改源码后需重新构建。
本地未提交修改会在 `BUILD.json` 标记 `git_dirty: true`，正式 Actions 发布要求干净提交。

已配置 Pulse 签名身份和公证凭据的维护者可执行：

```sh
sh scripts/build-macos.sh --developer-id
python3 scripts/package-signed-macos.py --notarize
```

Linux 可验证可移植核心和 CUPS 接口，需要 C 编译器、CMake、Python 3 和 CUPS 开发包：

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
ctest --test-dir build --output-on-failure

cmake -S . -B build-sanitize -DCMAKE_C_COMPILER=clang -DM1136_SANITIZE=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build-sanitize --parallel
ctest --test-dir build-sanitize --output-on-failure
```

测试覆盖 JBIG 一致性与解码回环、XQX 结构、每次输出失败、输入边界、500 页上限、
份数与计数、大小端、截断输入、取消竞态、阻塞管道、构建来源和版本一致性。
macOS 另有 10 种 Apple PDF → raster → XQX 管线测试。
详见 [验证记录与限制](docs/VALIDATION.md)。

## GitHub Actions 发布

- 普通 push / PR：原生构建、测试、sanitizer 和开发归档，不读取发布私钥。
- `v*` 标签：校验标签与 `VERSION` 一致且提交属于 main；运行测试，
  从 GitHub Secrets 导入临时钥匙串，签名驱动及 PKG，提交 Apple 公证。
- 只有公证 Accepted、票据和 Gatekeeper 检查通过、凭据清理完成后，才发布 Release。
  发布记录包含实际构建提交、宿主系统、签名团队、公证提交 ID 和文件摘要。

维护流程与 Secrets 名称见 [发布配置](docs/RELEASING.md)。构建和 CI 不安装、不创建队列、不打印。

## 实现与安全边界

```text
应用 / PDF → 系统 CUPS 渲染 → 未压缩 CUPS raster v1/v3
          → 页头预检查 → 4×4 有序抖动 → JBIG → PJL/XQX → 系统 USB backend
```

先验证页头再交给 CUPS；限制 raster 为 5200×8500、每行最多 8192 字节。
过滤器不把用户名、标题或任意选项拼入 PJL，不执行 shell、不访问网络或文档临时文件。
非阻塞 I/O 配合有限等待处理取消；JBIG 当前页的计算仍可能执行到返回。
发生中途错误时，已送入打印机的页面无法撤回，不应盲目自动重放。

[协议依据](docs/PROTOCOL.md)。本项目不是 DriverKit 实现，也不宣称经过完整商业安全审计。

## 许可证

GPL-2.0-or-later，见 [COPYING](COPYING)。分发二进制时请同时提供 Release 附带的对应源码归档。
JBIG-KIT 2.2 来自作者官方发布源，来源及逐文件摘要在 `vendor/jbigkit/SOURCE.json`，构建时核验。
库文件保持原样；官方自测程序的两处退出泄漏仅在生成的测试副本中补充释放。
JBIG 内部分配失败仍会 abort；过滤器禁止 core dump，由 CUPS 观察进程失败。
