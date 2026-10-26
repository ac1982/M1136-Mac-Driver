# M1136 手动双面

状态：1.1.0 本机测试包已通过 A4 四页、两张纸的长边双面实测，包含回放后按复印键继续。
短边、奇数页与取消恢复仍待实机验收。已公开的稳定版 1.0.0 不含此功能。

## 使用

打印窗口的打印机功能中选择 **Manual Duplex (1 copy; reload at H1)**：

- Off：单面。
- Long-edge binding：长边翻页，竖版文档通常选此项。
- Short-edge binding：短边翻页，例如竖版上翻日历。

份数设为 1，所有页面使用相同纸型、方向和图像尺寸。页序使用 Normal（正常）。
不要另外设置系统的自动双面。
驱动按最终排版后的 raster 页面配对；页码选择和每张多页等上游操作先完成。
需要多份时，请逐份提交完整任务，完成一份双面再提交下一份。

```sh
lp -d HP_M1136_Native_C -n 1 -o PageSize=A4 \
  -o M1136ManualDuplex=LongEdge document.pdf
```

第一遍为 1、3、5…，打印机收到第二遍的第一张时暂停。等待所有纸张落入出纸托盘、
面板显示 H1 后，再取出整叠纸。保持纸张原方向和上下顺序，已打印面朝下放回进纸仓，
不要逐张翻面或重新排序；先取走进纸仓中未使用的白纸。

放好整叠纸后，按打印机的复印键（Copy）继续打印背面；此动作已在本机实测确认。
本实现没有电脑端“继续”弹窗。
原厂说明使用电脑弹窗继续；不要把 M1210 的 OK 键说明套用到 M1136。
CUPS 可能在设备仍等待回放纸张时显示任务完成，以实际出纸和面板状态为准。

第二遍按偶数页倒序打印。例如 5 页文件使用 3 张纸：先 1、3、5，后空白、4、2，
配对为 1/2、3/4、5/空白。长边模式会旋转背面图像，回放纸张的动作保持一致。

每次最多 200 页/100 张（按出纸托盘容量限制），压缩暂存最多 512 MiB。
输入不完整、超过限制、混合纸型/图像尺寸或多份任务会在任何出纸之前报错。
输出过程中取消不能撤回设备已接收的数据；若仍在 H1 状态，使用打印机取消键结束当前任务，
确认设备就绪后再提交新任务。

## 依据

- [HP M1130/M1210 官方用户指南](https://h10032.www1.hp.com/ctg/Manual/c01760651.pdf)：
  印刷页 31–32 为 Mac 手动双面操作；第 193 页说明 M1130 系列 H1 是手动双面等待状态。
  正确型号为 LaserJet Professional M1136，不能混用较新的 HP Laser MFP 1136 手册。
- [惠普支持社区：M1136 手动双面](https://h30471.www3.hp.com/t5/da-yin-ji-shi-yong-xiang-guan-wen-ti/HP1136da-yin-ji-zaiwin10xi-tong-xia-bu-neng-shi-xian-shou-dong-shuang-mian-da-yin/td-p/1196991)：
  HP 支持工程师确认双面等待时显示 H1；该讨论未提供可直接用于本驱动的恢复协议。
- [OpenPrinting foo2xqx.c 固定版本](https://github.com/OpenPrinting/foo2zjs/blob/80499ed5bf6caa2963ad337e37cfda78a80aab1e/foo2xqx.c)
  和 [xqx.h](https://github.com/OpenPrinting/foo2zjs/blob/80499ed5bf6caa2963ad337e37cfda78a80aab1e/xqx.h)：
  XQX 暂停值、奇数页先印/偶数页倒序、长边旋转和补白逻辑的协议依据。
- [社区经历：foo2xqx 手动双面](https://unix.stackexchange.com/questions/150288/manual-duplex-printing)：
  P1005 用户报告过恢复不可靠，设备与 M1136 不同，因此不能用该经历代替本机验收。

## 验证

`tests/duplex.py` 独立解码真实输出的 JBIG 图像，核验奇偶配对、实际宽度旋转、
对齐白边、空白末面、暂停字段与份数；覆盖 1–4、199、200 页及 201 页拒绝。
损坏尾部、截断页面、混合纸型/尺寸、多份和无效模式均须在零输出时拒绝。
`tests/macos-pipeline.py` 额外覆盖 A4/Letter × 3/4 页 × 长边/短边共 8 种 Apple 渲染场景。

2026-10-26，本机 Pulse 签名并经 Apple 公证的 1.1.0 驱动通过 Word 提交四页 A4 文档，
设置 1 份、Normal 页序、LongEdge。用户确认两张纸的正反面内容和方向完全正常，
并确认放回纸后按打印机复印键继续。

实机验收仍需：短边翻页、奇数页补白、Letter、横向页面与取消后恢复。
