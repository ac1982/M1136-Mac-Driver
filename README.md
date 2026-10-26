# M1136 Mac Driver

原生 C 的 HP LaserJet Professional M1136 USB 打印驱动。
目标：Apple Silicon / macOS 27.0.1（26A434），不依赖 Rosetta，不增加网络打印服务。

**当前为待实机验收的开发版本。软件测试通过不等于已经验证真实出纸。**
扫描功能不在本项目范围内。

## 实现

驱动业务代码独立编写，仅复用官方 JBIG-KIT 2.2 压缩库。
不包含或链接旧驱动，不使用其 CLI、shell wrapper、下载工具或 hotplug 服务。

```text
Mac 打印应用 / PDF
    ↓ 系统 CUPS 渲染
未压缩 CUPS raster (v1/v3)
    ↓ raster_input.c：先检查页头，再调用系统 CUPS 读取
    ↓ page.c：固定 4×4 有序抖动，按 128 像素补齐
    ↓ codec.c：JBIG-KIT 单平面压缩，64 KiB 固定输出缓冲
    ↓ xqx.c：任务状态、PJL/XQX 大端序列化
系统 CUPS USB backend → M1136
```

`filter.c` 管理任务、输入文件、取消、输出和资源释放。
核心通过写入回调输出，协议和图像模块不依赖 CUPS，不执行进程、不访问网络或文档临时文件。

支持 600dpi、8-bit white grayscale、A4/Letter、单面、1–99 份、最多 500 页；
光栅上限 5200×8500，行字节上限 8192。拒绝压缩 raster 容器、彩色和双面。
PPD 使用 12pt 可打印边界，定位和打印效果仍需设备校准。

## 构建与测试

在原生 Apple Silicon Mac 上准备 Xcode Command Line Tools、CMake 和 Python 3：

```sh
sh scripts/build-macos.sh
python3 scripts/package-macos.py
```

构建不联网下载依赖。安装包位于 `build-package/`；
详见 [安装与回滚](docs/INSTALL.zh-CN.md)。构建与 CI 不安装驱动、不创建打印队列、不打印。
运行时仅链接 macOS libcups 与 libSystem；压缩库静态链接，解码路径从发行过滤器移除。

Linux 可用于可移植核心和 CUPS 接口验证，需要 C 编译器、CMake、Python 3、CUPS 开发包：

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
ctest --test-dir build --output-on-failure

cmake -S . -B build-sanitize -DCMAKE_C_COMPILER=clang -DM1136_SANITIZE=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build-sanitize --parallel
ctest --test-dir build-sanitize --output-on-failure
```

GitHub Actions 使用固定提交的 Actions，在 macOS ARM64 上执行原生构建、
测试、Apple PDF 管线和打包。成功运行会提供带构建提交信息的安装包 artifact。

## 验证与边界

- 官方 JBIG T.82 一致性测试；图像压缩/解码回环，包含超过 64 KiB 的多片输出。
- XQX 结构、页面尺寸、灰度抖动、输出每个写入位置的失败处理。
- A4、Letter、多页、500 页边界、极端尺寸、非法参数、残缺头及像素、字节序。
- 输入文件类型、断开的输出管道、SIGTERM 取消及固定种子的异常流。
- [测试记录与已知限制](docs/VALIDATION.md)；[协议依据](docs/PROTOCOL.md)。

目标系统版本、USB 出纸、边距、灰阶、真实多份排序、取消后的设备恢复仍需实机验证。
不是经过完整审计的成熟商业驱动，也不是 DriverKit 实现。

## 依赖与许可证

JBIG-KIT 2.2 来自作者官方 HTTPS 发布源，完整来源与字节摘要记录于
`vendor/jbigkit/SOURCE.json`；配置时逐文件检查摘要。摘要固定字节，不提供独立作者签名认证。

JBIG 库文件保持原样。官方测试程序有两处退出时漏释放，构建时仅对生成的测试副本添加释放；
没有禁用 LeakSanitizer，也没有修改压缩库。
JBIG 内部分配失败仍会 `abort()`；过滤器禁止 core dump，由 CUPS 观察进程失败。

本项目采用 GPL-2.0-or-later，见 [COPYING](COPYING)，第三方版权声明保留在源码中。
