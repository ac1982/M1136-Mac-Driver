# M1136 Mac Driver

原生 C 的 HP LaserJet Professional M1136 USB 打印过滤器。
目标：Apple Silicon / macOS 27.0.1（26A434），无 Rosetta，无网络打印服务。

当前为开发版本，尚未在目标 macOS 或真实打印机验证。扫描不在范围内。

设计：CUPS raster → 有界灰度处理 → JBIG-KIT → PJL/XQX → 系统 USB backend。
协议依据为 OpenPrinting/foo2zjs 的可观察实现，而非完整厂商规范。
不包含旧驱动的 CLI、shell wrappers、下载或 hotplug 路径。

JBIG-KIT 2.2 从作者 HTTPS 发布源获取，未修改，摘要见 vendor/jbigkit/SOURCE.json。
摘要固定下载字节，不等于独立签名认证。项目按 GPL-2.0-or-later 发布，见 COPYING。
