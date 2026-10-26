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
