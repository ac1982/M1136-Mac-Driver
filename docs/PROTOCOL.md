# 协议依据与边界

参考：OpenPrinting/foo2zjs，提交 80499ed5bf6caa2963ad337e37cfda78a80aab1e，
foo2xqx.c 与 xqx.h。新驱动独立实现序列化，不包含旧驱动代码。
https://github.com/OpenPrinting/foo2zjs/tree/80499ed5bf6caa2963ad337e37cfda78a80aab1e

PJL 包裹 XQX；魔数 `,XQX`；所有整数按 big endian 写入，不序列化 C struct。
记录：1/2 文档起止，3/4 页面起止，5/6 压缩平面片段起止，7 JBIG 数据。
普通记录第二个 uint32 为 item 数；JBIG 记录为后续字节数。
Item 为 type/size/value，整数值长度 4。终结 item 0x80000001=0xdeadbeef。
JBIG 第一段 BIH 20 字节，数据按最多 65536 字节分片；第一片携带 BIH，
后续片以 0x40000003=1 延续。图像宽度向上补齐到 128 像素；video width 保留实际宽度。
JBIG 使用单平面、L0=128、MX=MY=0；MX=0 是已知 M1136 兼容参数。
600dpi，A4=9、Letter=1，auto source=7、plain media=1、simplex。
未知字段保留参考实现值，不假称已理解其厂商语义。

协议结构测试、压缩回环、旧编码器差分不能替代真实设备验证。

## 核心接口约定

`m1136_page_create` 的输出必须是新的或已经 destroy 的 page，成功后由调用者
在所有退出路径调用 `m1136_page_destroy`。灰度 0 表示黑色，255 表示白色；
补齐像素置白。调用方不能修改 page 的尺寸、stride 或存储指针。

任务用 begin → page（1..500 次）→ end；begin 初始化新的任务上下文。
写入回调必须完整消费所有字节后才返回 0；失败后任务进入永久错误状态，不能继续输出。
开始输出后的错误可能留下部分任务，调用方不能把错误隐藏为成功或直接自动重试。
驱动自行管理信号，核心没有进程级退出、shell 调用或设备 I/O。

每页份数由已验证的 raster `NumCopies`（1–99）传给 `m1136_job_page`，
同时用于 XQX COPIES 和 CUPS `PAGE:` 计数。命令行份数仍校验，但不再重复施加：
Apple renderer 可能已把逐份任务展开为多页，每个页头 NumCopies=1。

## 手动双面（1.1.0 起）

参考同一固定版本 foo2xqx.c 的 start_doc、start_page 和末尾手动双面分支，独立实现：
文档 item `0x10000002=2`；页面添加 `0x20000012`，item 数从 15 变为 16，
长度字段从 180 变为 192。暂停值依次为首个正面 0、后续正面 1、首个背面 2、后续背面 3。
打印次序为奇数页升序、偶数页降序；奇数页数先补白。长边装订偶数页旋转 180°，
只旋转实际可见矩形，补齐到 128 像素的右侧白边不进入旋转。

自定义 PPD 选项 `M1136ManualDuplex=Off/LongEdge/ShortEdge` 不设置 raster Duplex/Tumble，
避免上游做第二次旋转。只接受同纸型、同图像尺寸、单份任务；最多 200 页，压缩暂存 512 MiB。
临时文件由 cupsTempFd 创建并立即取消目录链接，FD_CLOEXEC，所有退出路径 close。
只保存本进程生成的压缩平面记录；回放时由序列化器重新生成页面头和暂停字段。

协议及像素自动测试已通过。本机 1.1.0 的 A4 四页长边双面输出已获用户确认：
整叠回放后按复印键继续，正反配对和文字方向正常。短边与奇数页仍待实物确认。
详见 [手动双面说明](MANUAL-DUPLEX.zh-CN.md)。
