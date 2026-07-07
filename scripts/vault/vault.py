#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
加密保险库 — 文件级存储

支持两种模式：
  .enc   — RSA-OAEP 加密，敏感数据（私钥在少爷浏览器里）
  .txt   — 明文存储，重要但无需加密的数据（订单号、配置等）

文件结构：
  MEMORY/vault/
    ├── 币安API.enc          ← 加密文件
    ├── Mac_Studio订单.txt   ← 明文文件
    └── plain/               ← 明文文件存储目录

加密/解密由 vault.html 在浏览器本地完成（Web Crypto API）。
本脚本负责文件的存取管理。

用法：
  python vault.py list                         列出所有条目
  python vault.py save <标签> <文件路径>        保存 .enc 文件
  python vault.py encrypt <标签> <明文内容>     直接用公钥加密并保存
  python vault.py save --text <标签> <内容>     保存明文 .txt 文件
  python vault.py get <标签>                    输出 .enc 文件内容（base64）
  python vault.py get --text <标签>             输出 .txt 文件内容
  python vault.py delete <标签>                 删除条目
"""

import os
import sys
import base64

# ── 加密库 ────────────────────────────────────────────
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VAULT_DIR = SKILL_DIR / "MEMORY" / "vault"
PLAIN_DIR = VAULT_DIR / "plain"
PUBKEY_PATH = SKILL_DIR / "assets" / "vault_public_key.pem"


def cmd_encrypt(label: str, content: str):
    """用公钥加密明文并直接保存为 .enc 文件"""
    if not CRYPTO_OK:
        print("❌ 需要 cryptography 库。请执行: pip install cryptography")
        sys.exit(1)
    if not PUBKEY_PATH.exists():
        print(f"❌ 未找到公钥: {PUBKEY_PATH}")
        sys.exit(1)

    with open(PUBKEY_PATH, "rb") as f:
        pubkey = serialization.load_pem_public_key(f.read(), backend=default_backend())

    ciphertext = pubkey.encrypt(
        content.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_label(label)
    dst = VAULT_DIR / f"{safe}.enc"
    with open(dst, "wb") as f:
        f.write(ciphertext)
    print(f"✅ 已加密保存: {dst.name}  ({len(ciphertext)} bytes)")


def _safe_label(label: str) -> str:
    return label.replace("/", "_").replace("\\", "_").replace(":", "_")


def cmd_list():
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    PLAIN_DIR.mkdir(parents=True, exist_ok=True)

    enc_files = sorted(VAULT_DIR.glob("*.enc"))
    txt_files = sorted(PLAIN_DIR.glob("*.txt"))

    if not enc_files and not txt_files:
        print("保险库为空。")
        return

    if enc_files:
        print("🔒 加密条目：")
        for f in enc_files:
            size = f.stat().st_size
            print(f"    📄 {f.stem}  ({size:,} bytes)")
    if txt_files:
        print("📝 明文条目：")
        for f in txt_files:
            size = f.stat().st_size
            print(f"    📄 {f.stem}  ({size:,} bytes)")


def cmd_save(label: str, src_path: str):
    src = Path(src_path)
    if not src.exists():
        print(f"❌ 源文件不存在: {src}")
        sys.exit(1)
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_label(label)
    dst = VAULT_DIR / f"{safe}.enc"
    with open(src, "rb") as f:
        data = f.read()
    with open(dst, "wb") as f:
        f.write(data)
    print(f"✅ 已保存: {dst.name}  ({len(data):,} bytes)")


def cmd_save_text(label: str, content: str):
    PLAIN_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_label(label)
    dst = PLAIN_DIR / f"{safe}.txt"
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 已保存: {dst.name}  ({len(content)} 字)")


def cmd_get(label: str):
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_label(label)
    f = VAULT_DIR / f"{safe}.enc"
    if not f.exists():
        print(f"❌ 未找到: {safe}.enc")
        sys.exit(1)
    with open(f, "rb") as fh:
        data = fh.read()
    print(base64.b64encode(data).decode("ascii"))


def cmd_get_text(label: str):
    PLAIN_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_label(label)
    f = PLAIN_DIR / f"{safe}.txt"
    if not f.exists():
        print(f"❌ 未找到: {safe}.txt")
        sys.exit(1)
    with open(f, "r", encoding="utf-8") as fh:
        print(fh.read())


def cmd_delete(label: str):
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    PLAIN_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_label(label)
    deleted = False
    for d, ext in [(VAULT_DIR, ".enc"), (PLAIN_DIR, ".txt")]:
        f = d / f"{safe}{ext}"
        if f.exists():
            f.unlink()
            print(f"🗑️  已删除: {f.name}")
            deleted = True
    if not deleted:
        print(f"❌ 未找到: {safe}.enc 或 {safe}.txt")


def usage():
    print("加密保险库 — 文件级存储")
    print()
    print("  python vault.py list")
    print("  python vault.py save <标签> <文件路径>")
    print("  python vault.py encrypt <标签> <明文内容>")
    print("  python vault.py save --text <标签> <内容>")
    print("  python vault.py get <标签>            # 输出 base64（加密文件）")
    print("  python vault.py get --text <标签>     # 输出明文（明文文件）")
    print("  python vault.py delete <标签>")


def main():
    if len(sys.argv) < 2:
        usage()
        return

    cmd = sys.argv[1]

    if cmd == "list":
        cmd_list()

    elif cmd == "encrypt":
        if len(sys.argv) < 4:
            print("❌ 需要: python vault.py encrypt <标签> <明文内容>")
            sys.exit(1)
        cmd_encrypt(sys.argv[2], sys.argv[3])

    elif cmd == "save":
        if len(sys.argv) >= 3 and sys.argv[2] == "--text":
            if len(sys.argv) < 5:
                print("❌ 需要: python vault.py save --text <标签> <内容>")
                sys.exit(1)
            cmd_save_text(sys.argv[3], sys.argv[4])
        else:
            if len(sys.argv) < 4:
                print("❌ 需要: python vault.py save <标签> <文件路径>")
                sys.exit(1)
            cmd_save(sys.argv[2], sys.argv[3])

    elif cmd == "get":
        if len(sys.argv) >= 3 and sys.argv[2] == "--text":
            if len(sys.argv) < 4:
                print("❌ 需要: python vault.py get --text <标签>")
                sys.exit(1)
            cmd_get_text(sys.argv[3])
        else:
            if len(sys.argv) < 3:
                print("❌ 需要: python vault.py get <标签>")
                sys.exit(1)
            cmd_get(sys.argv[2])

    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("❌ 需要: python vault.py delete <标签>")
            sys.exit(1)
        cmd_delete(sys.argv[2])

    else:
        print(f"未知命令: {cmd}")
        usage()


if __name__ == "__main__":
    main()
