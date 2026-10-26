# 验证记录与限制

日期：2026-10-26。每个测试结果仅适用于实际测试的系统与源码版本。

## Linux ARM64

Clang 21.1.8，CUPS 2.4.16。

- 普通构建：JBIG 官方一致性、核心、CUPS 集成三组全部通过。
- ASan + UBSan：三组全部通过，Linux 默认 LeakSanitizer 保持启用。
- Clang 静态分析：五个驱动 C 源文件未报告诊断。
- 发行符号检查：未链接 JBIG 解码、system/popen/execve、socket、tmpfile 指定符号。

静态符号检查只覆盖过滤器本身，不表示 libcups、系统 USB backend 或整个系统没有这些功能。

## macOS ARM64 CI

实现提交：`e69f89068137d59123b35f0e60effb473e0a0b52`。
[成功运行记录](https://github.com/ac1982/M1136-Mac-Driver/actions/runs/40269983055)。
实际宿主：macOS **26.6.2（25G83）**、ARM64；不是用户指定的 27.0.1（26A434）。

- Release 编译及三组测试通过。
- ASan + UBSan 编译及三组测试通过。macOS 上 LeakSanitizer 支持与 Linux 不同；泄漏验证以 Linux 结果为准。
- ARM64 架构、ad-hoc 签名、PPD 检查通过。
- 直接动态依赖仅 `/usr/lib/libcups.2.dylib` 与 `/usr/lib/libSystem.B.dylib`。
- Apple 系统 cupsfilter：A4 和 Letter PDF → raster → XQX 均通过。
- 安装包已生成并上传；下载后逐项 SHA-256 检查通过。
- 安装脚本只做语法检查和代码审查，没有在 CI 创建打印队列或安装到系统。

安装包：`M1136-Mac-Driver-arm64.tar.gz`，构建提交在包内 `BUILD.json`。
此运行安装包 SHA-256：
`fda60b08b4783101456818c884e2ab59c5cf4386b13c3fa4a91e6cce3f92ef30`。
GitHub artifact 保留 30 天；可以从固定提交重新本地构建。

## 测试设计

`tests/core.c` 独立解析生成的 XQX 字段，重组 BIH + 数据，再调用解码器逐字节比较页面。
大幅噪声图像用于验证多片压缩输出；逐次注入输出失败验证错误不会丢失。
解码器只用于测试程序，不进入发行过滤器。

`tests/filter.py` 检查 500/501 页、最大尺寸、A4/Letter、1/99 份、不同字节序与 v1/v3；
拒绝溢出尺寸、彩色、双面、错误 stride、错误纸型/分辨率/位深、截断头/像素、损坏尾部；
并验证符号链接/FIFO/目录拒绝、管道断开、等待输入时取消。
60 个固定随机种子异常流主要检验非法 magic 路径，不是完整 fuzzing。

`tests/macos-pipeline.py` 自制 A4/Letter PDF，经系统 cupsfilter 转 raster，再运行过滤器。
它检查软件转换和任务完整结束，无法证明打印机已接收。

## 明确限制

- 尚无用户目标 macOS 27.0.1（26A434）和 HP M1136 实物打印记录。
- 仅接受未压缩 CUPS raster v1/v3；压缩容器在读取 magic 时拒绝。
- 必须使用系统 CUPS 库；预检查限制页头尺寸，但这不是对系统库的完整审计。
- JBIG-KIT 内部分配失败使用 abort；核心自己的分配和输出错误显式返回。
- 取消时不再写后续数据；JBIG 当前页的计算可能继续到其返回，输入尺寸已有上限。
- 中途损坏或断开不能撤回已经送到打印机的页面。失败任务不要自动重放以免重复出纸。
- 没有自实现 USB backend；设备断开恢复与 CUPS 重试策略仍需实机验证。
- 12pt 页边距、打印密度、灰阶效果、份数排序需要设备确认。
- 软件兼容性依据来自可观察协议行为，不是完整厂商协议规范。

