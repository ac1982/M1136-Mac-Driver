# 发布配置

普通 CI 使用 ad-hoc 构建；正式签名发布仅由 `v*` 标签触发，不能从 PR 读取发布 Secrets。

## 仓库 Secrets

| 名称 | 内容 |
|---|---|
| `APPLE_APPLICATION_P12_BASE64` | Pulse Developer ID Application 加密 P12 的 base64 |
| `APPLE_INSTALLER_P12_BASE64` | Pulse Developer ID Installer 加密 P12 的 base64 |
| `APPLE_P12_PASSWORD` | 两份 P12 的解密密码 |
| `APPLE_NOTARY_KEY_BASE64` | App Store Connect 公证 API P8 私钥的 base64 |
| `APPLE_NOTARY_KEY_ID` | API Key ID |
| `APPLE_NOTARY_ISSUER_ID` | API Issuer ID |

Secrets 通过 GitHub 加密存储，不写入仓库、命令输出、artifact 或源码归档。
CI 从 Apple 官方源获取匹配的 Developer ID G1 中间证书并核对固定 SHA-256，再导入临时钥匙串；不修改系统信任设置。
签名任务只有 contents:read；发布任务独立授予 contents:write，且不接收 Apple 私钥。
CI helper 在 runner 临时目录创建钥匙串，导入后删除 P12/P8 临时文件，always 步骤清理钥匙串。
不要使用 pull_request_target 执行不可信 PR 代码并传入这些 Secrets。

本机签名使用已有专用钥匙串；CI 从备份恢复到临时钥匙串，不需要本机钥匙串密码。
证书续期后需同步 Secrets，并更新 `scripts/sign-macos.py` 中的精确 Application 指纹。
当前 Pulse Developer ID 证书到期时间为 2027-02-01 22:12:15 UTC，发布前需核查实际有效期。

## 版本与发布

1. 更新 `VERSION` 和 PPD FileVersion，补充对应版本的 release notes。
2. 运行测试，提交并推送 main；保持工作区干净。
3. 创建并推送与 VERSION 相同的标签，例如 `v1.0.0`。
4. 等待 Signed release workflow 成功，检查 Release 的 PKG、摘要、源码与发布报告。

发布工作流读取 `docs/RELEASE-<VERSION>.md`；每个版本需提交对应发布说明。
Actions 从标签源码重新构建，不能把本机实测等同于对每个 CI 二进制做过物理打印。
公证失败不会发布。若上传中断，先查看报告中的 submission_id，避免盲目重复提交。
若创建草稿 Release 后上传或发布失败，先检查并处理该草稿，再重新执行发布步骤，不覆盖已发布版本。

macOS 安装包签名使用 Developer ID Installer，内部程序使用 Developer ID Application、
hardened runtime 与可信时间戳；最终校验和在公证票据装订后生成。
