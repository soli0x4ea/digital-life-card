#!/usr/bin/env python3
"""
天书加密 (Tianshu Crypt) — TianshuV2 算法 Python 实现
======================================================
基于 D:\\soli\\天书精简版\\S.cs 中 TianshuV2 类的完整移植。
保留汉字替换视觉特色 + 盐值 + 流式多表替换 + HMAC 认证。

密文格式（汉字序列）：
    [头标"天玄"4字][盐值32字][密文n字][HMAC16字][尾标"地黄"4字]
"""

import os
import sys
import hmac
import hashlib
import argparse


# ============================================================
# 256 汉字单字映射表（来自 C# IntToChinCode）
# ============================================================
INT_TO_HANZI = [
    "零","壹","贰","叁","肆","伍","陆","柒",
    "捌","玖","拾","佰","仟","万","亿",
    "东","南","西","北","中","色","即",
    "是","空","天","地","风","雨","雷",
    "电","雾","霜","雪","金","木","水",
    "火","土","阴","阳","行","生","死",
    "郭","际","自","然","我","意","识",
    "微","小","大","神","灵","无","阿",
    "弥","陀","佛","相","心","由","道",
    "法","吾","悟","山","海","苍","茫",
    "极","宇","宙","源","鬼","兽","花",
    "仁","毁","灭","灰","烬","者","使",
    "命","运","动","静","止","子","爱",
    "倩","钱","财","玉","鸟","鱼","虫",
    "飞","游","数","定","点","线","面",
    "时","间","物","质","能","量","盗",
    "恨","情","仇","知","铃","音","波",
    "刚","般","若","罗","蜜","念","欲",
    "世","问","奈","何","星","宿","不",
    "朽","旋","转","幽","冥","咆","哮",
    "鼠","牛","虎","兔","龙","蛇","马",
    "羊","猴","鸡","狗","猪","猫","白",
    "黑","青","朱","雀","玄","武","魔",
    "魂","血","圣","精","传","一","二",
    "三","四","五","六","七","八","九",
    "十","腐","烂","银","王","胜","败",
    "寇","黄","红","绿","蓝","澄","紫",
    "米","民","食","蛟","乌","岛","仙",
    "今","昔","兮","明","月","几","有",
    "把","酒","唐","光","暗","影","竹",
    "林","松","善","上","下","舟","咒",
    "曰","日","回","来","将","皇","丝",
    "远","近","尽","头","尾","宫","缰",
    "降","落","彩","虹","圆","方","织",
    "季","家","国","人","怂","萌","试",
    "刀","剑","枪","炮","炎","器","奇",
    "力","为","铁"
]

# 构建反向查找表：汉字 → 索引 (0-255)
HANZI_TO_INDEX = {hz: i for i, hz in enumerate(INT_TO_HANZI)}

HEAD_MARK = "TZXZ"   # 4 ASCII 字符（头标协议标志）
TAIL_MARK = "DHNG"   # 4 ASCII 字符（尾标协议标志）
SALT_BYTES = 32
HMAC_BYTES = 16
HEAD_CHARS = 4
TAIL_CHARS = 4


def _derive_base_key(salt: bytes, password: str) -> bytes:
    """派生基础密钥：SHA256(盐值 + UTF-16-LE(密码))"""
    pw_bytes = password.encode("utf-16-le")
    combined = salt + pw_bytes
    return hashlib.sha256(combined).digest()


def _per_position_permutation(base_key: bytes, position: int) -> list:
    """使用 SHA256(基础密钥 + position) 生成第 position 位的置换表"""
    pos_bytes = base_key + position.to_bytes(4, byteorder="little")
    pos_hash = hashlib.sha256(pos_bytes).digest()
    # 对 0-255 排序，以 pos_hash 为比较键
    indices = list(range(256))
    # 将 hash 字节扩展为排序键
    sort_keys = []
    for i in range(256):
        key = 0
        for j in range(32):
            key = (key << 8) | (pos_hash[(i * 31 + j) % 32] ^ (i + 1))
        sort_keys.append(key)
    indices.sort(key=lambda x: sort_keys[x])
    return indices


def encrypt_bytes(data: bytes, password: str) -> bytes:
    """
    流式加密（返回二进制密文，未经汉字编码）
    
    输出格式：[HEAD(4B)][Salt(32B)][CipherData(nB)][HMAC(16B)][TAIL(4B)]
    """
    # 1. 随机盐值
    salt = os.urandom(SALT_BYTES)

    # 2. 派生基础密钥
    base_key = _derive_base_key(salt, password)

    # 3. 流式多表替换加密
    cipher_data = bytearray(len(data))
    for i in range(len(data)):
        perm = _per_position_permutation(base_key, i)
        cipher_data[i] = perm[data[i]]

    # 4. HMAC-SHA256(密文 + 盐值, 密码) 取前 16 字节
    hmac_input = bytes(cipher_data) + salt
    pw_bytes = password.encode("utf-16-le")
    hmac_full = hmac.new(pw_bytes, hmac_input, "sha256").digest()
    hmac_trunc = hmac_full[:HMAC_BYTES]

    # 5. 组装：[HEAD][Salt][CipherData][HMAC][TAIL]
    head_bytes = HEAD_MARK.encode("ascii")
    tail_bytes = TAIL_MARK.encode("ascii")

    result = bytearray()
    result.extend(head_bytes)
    result.extend(salt)
    result.extend(cipher_data)
    result.extend(hmac_trunc)
    result.extend(tail_bytes)

    return bytes(result)


def decrypt_bytes(data: bytes, password: str) -> bytes:
    """
    流式解密（自动验证 HMAC）
    输入为二进制密文（含头标/盐值/HMAC/尾标）
    """
    if len(data) < 4 + SALT_BYTES + HMAC_BYTES + 4:
        raise ValueError("密文长度不足")

    offset = 0

    # 1. 验证头标
    head = data[offset:offset+4].decode("ascii")
    offset += 4
    if head != HEAD_MARK:
        raise ValueError("无效的头标，数据可能损坏")

    # 2. 提取盐值
    salt = data[offset:offset+SALT_BYTES]
    offset += SALT_BYTES

    # 3. 提取密文
    cipher_len = len(data) - 4 - SALT_BYTES - HMAC_BYTES - 4
    cipher_data = data[offset:offset+cipher_len]
    offset += cipher_len

    # 4. 提取 HMAC
    stored_hmac = data[offset:offset+HMAC_BYTES]
    offset += HMAC_BYTES

    # 5. 验证尾标
    tail = data[offset:offset+4].decode("ascii")
    if tail != TAIL_MARK:
        raise ValueError("无效的尾标，数据可能损坏")

    # 6. 验证 HMAC
    hmac_input = cipher_data + salt
    pw_bytes = password.encode("utf-16-le")
    hmac_full = hmac.new(pw_bytes, hmac_input, "sha256").digest()
    if not hmac.compare_digest(hmac_full[:HMAC_BYTES], stored_hmac):
        raise ValueError("HMAC 验证失败，数据已被篡改或密码错误")

    # 7. 派生基础密钥
    base_key = _derive_base_key(salt, password)

    # 8. 流式多表替换解密
    plain_data = bytearray(cipher_len)
    for i in range(cipher_len):
        perm = _per_position_permutation(base_key, i)
        # 反向查找：perm[plain_byte] = cipher_byte → plain_byte = perm.index(cipher_byte)
        plain_data[i] = perm.index(cipher_data[i])

    return bytes(plain_data)


def encode_to_hanzi(data: bytes) -> str:
    """将二进制数据编码为汉字序列"""
    return "".join(INT_TO_HANZI[b] for b in data)


def decode_from_hanzi(hanzi_str: str) -> bytes:
    """将汉字序列解码为二进制数据"""
    result = bytearray(len(hanzi_str))
    for i, ch in enumerate(hanzi_str):
        if ch not in HANZI_TO_INDEX:
            raise ValueError(f"无法识别的汉字: '{ch}'")
        result[i] = HANZI_TO_INDEX[ch]
    return bytes(result)


def text_encrypt(plain_text: str, password: str) -> str:
    """文本加密：明文 → 天书汉字密文"""
    if not plain_text:
        return ""
    data = plain_text.encode("utf-16-le")
    encrypted = encrypt_bytes(data, password)
    return encode_to_hanzi(encrypted)


def text_decrypt(cipher_text: str, password: str) -> str:
    """文本解密：天书汉字密文 → 明文"""
    if not cipher_text:
        return ""
    encrypted = decode_from_hanzi(cipher_text)
    decrypted = decrypt_bytes(encrypted, password)
    return decrypted.decode("utf-16-le")


def file_encrypt(input_path: str, password: str, output_path: str) -> None:
    """文件加密：任意文件 → 天书汉字密文文件"""
    with open(input_path, "rb") as f:
        data = f.read()
    encrypted = encrypt_bytes(data, password)
    hanzi_output = encode_to_hanzi(encrypted)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(hanzi_output)
    print(f"[OK] 文件已加密 → {output_path}")
    print(f"     原始大小: {len(data)} 字节")
    print(f"     密文长度: {len(hanzi_output)} 汉字")


def file_decrypt(input_path: str, password: str, output_path: str) -> None:
    """文件解密：天书汉字密文文件 → 还原文件"""
    with open(input_path, "r", encoding="utf-8") as f:
        hanzi_input = f.read().strip()
    encrypted = decode_from_hanzi(hanzi_input)
    decrypted = decrypt_bytes(encrypted, password)
    with open(output_path, "wb") as f:
        f.write(decrypted)
    print(f"[OK] 文件已解密 → {output_path}")
    print(f"     还原大小: {len(decrypted)} 字节")


def show_info() -> None:
    """显示版本和算法信息"""
    print("=" * 60)
    print("  天书加密 v2.0 (TianshuV2)")
    print("  Stream Multi-Table Substitution Cipher")
    print("=" * 60)
    print()
    print("  算法特征:")
    print("    • 256 汉字单字映射表（复用原版 IntToChinCode）")
    print("    • 32 字节随机盐值（每次加密结果唯一）")
    print("    • 流式多表替换（每位置独立置换表，抗频率分析）")
    print("    • HMAC-SHA256 消息认证（前 16 字节）")
    print("    • 头标: 天玄 | 尾标: 地黄")
    print()
    print("  密文格式: [天玄4][盐值32][密文][HMAC16][地黄4]")
    print("  密码编码: UTF-16-LE (与 C# Encoding.Unicode 兼容)")
    print()
    print("  来源: D:\\soli\\天书精简版\\S.cs → TianshuV2")
    print("  本文件: ~/.workbuddy/skills/天书加密/scripts/tianshu_crypt.py")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="天书加密 (TianshuV2) — 汉字替换 + 流式多表 + HMAC 认证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s encrypt --text "Hello 世界" --password "mykey"
  %(prog)s decrypt --text "天玄天地..." --password "mykey"
  %(prog)s encrypt --file secret.bin --password "mykey" --output cipher.txt
  %(prog)s decrypt --file cipher.txt --password "mykey" --output restored.bin
  %(prog)s --info
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="操作: encrypt | decrypt")

    # encrypt
    enc = subparsers.add_parser("encrypt", help="加密")
    enc_group = enc.add_mutually_exclusive_group(required=True)
    enc_group.add_argument("--text", help="待加密的明文文本")
    enc_group.add_argument("--file", help="待加密的文件路径")
    enc.add_argument("--password", "-p", required=True, help="加密密码")
    enc.add_argument("--output", "-o", help="输出文件路径（可选，默认输出到控制台）")

    # decrypt
    dec = subparsers.add_parser("decrypt", help="解密")
    dec_group = dec.add_mutually_exclusive_group(required=True)
    dec_group.add_argument("--text", help="待解密的汉字密文")
    dec_group.add_argument("--file", help="汉字密文文件路径")
    dec.add_argument("--password", "-p", required=True, help="解密密码")
    dec.add_argument("--output", "-o", help="输出文件路径（可选，默认输出到控制台）")

    parser.add_argument("--info", action="store_true", help="显示版本和算法信息")

    args = parser.parse_args()

    if args.info:
        show_info()
        return

    if args.command == "encrypt":
        if args.text:
            result = text_encrypt(args.text, args.password)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result)
                print(f"[OK] 密文已写入 → {args.output}")
            else:
                print(result)
        elif args.file:
            if not args.output:
                print("[ERROR] 文件加密必须指定 --output", file=sys.stderr)
                sys.exit(1)
            file_encrypt(args.file, args.password, args.output)

    elif args.command == "decrypt":
        if args.text:
            result = text_decrypt(args.text, args.password)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result)
                print(f"[OK] 明文已写入 → {args.output}")
            else:
                print(result)
        elif args.file:
            if not args.output:
                print("[ERROR] 文件解密必须指定 --output", file=sys.stderr)
                sys.exit(1)
            file_decrypt(args.file, args.password, args.output)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
