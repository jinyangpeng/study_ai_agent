# -*- coding: utf-8 -*-
"""
Windows 姘撻檱鑱¤寘鑱欒仯蹇欒伋楣垮繖闅嗚仮鑼傚綍鑱akefile 姘撹伖?Windows 鐩茶祩鑱よ寘鑱硅仚鐚▌鑱涜寘鍨勮伜姘撻檱鑱虫皳搴愯仯鐚嫝鑱熻寕褰曡仯

蹇欒仺绡撶尗鑱ц伂鐩插綍鑱垫皳鑱熻仮鐩查檰椹磋幗鑱扮瘬:
  pip install -e .     # 姘撳簮鑱ｇ尗鎷㈣仧姘撹伂鑱ㄦ皳鑱倝鑾借伕楹撳繖鑱ㄦゼ鐚┐鑱尗闅嗚仸: dev / prod / lint / fmt
  make <姘撹伃闄嗙洸绂勯檱>          # macOS/Linux 蹇欒仺绡撶尗鑱ц伂

Windows 蹇欒伌?make 蹇欒伌闇茬洸闄嗛┐鑾借伆?
  python scripts.py <姘撹伃闄嗙洸绂勯檱>

姘撹伀鐐夎幗鑱扮瘬姘撹伃闄嗙洸绂勯檱:
  init    - 鐩茶祩鑱欒寘鑱板簮姘撹仮鑱烘皳鎼傝仴姘撹仸鑱宠寘闅嗛箍鑾借伕搴愯寕褰曡仮鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨?+ 鐩叉埉鑱虹尗纰岃伋 + .env鑼傚綍?
  dev     - 鐩茬妤兼皳褰曡仚姘撹伀鑱幗鑱ㄧ倝姘撳瀯鑱濈尗椹磋伂鐚殕鑱﹁寘闅嗛箍鑾借伕?
  prod    - 鐩茬妤艰幗鑱拌伡鐩叉綖鎼傝幗鑱ㄧ倝姘撳瀯鑱濈尗椹磋伂鐚殕鑱﹁寘闅嗛箍鑾借伕?
  install - 姘撳簮鑱ｇ尗鎷㈣仧鑼呴殕楣胯幗鑱稿簮鐩叉埉鑱虹尗纰岃伋
"""

import subprocess
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"


def _python() -> str:
    """鐚仺璺皳鑱伋鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨勮仢鐩茶祩棰呰幗鑱疯仦 python 鐚矾鐐夋皳鎴仦"""
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "python")
    return str(VENV_DIR / "bin" / "python")


def _pip() -> str:
    """鐚仺璺皳鑱伋鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨勮仢鐩茶祩棰呰幗鑱疯仦 pip 鐚矾鐐夋皳鎴仦"""
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "pip")
    return str(VENV_DIR / "bin" / "pip")


def _run(cmd: str, env_extra: dict | None = None):
    """蹇欒仯鎼傜尗闅嗚仸姘撹伃闄嗙洸绂勯檱"""
    env = {**os.environ, **(env_extra or {})}
    result = subprocess.run(cmd, shell=True, cwd=BASE_DIR, env=env)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _ensure_venv():
    """鑾介殕搴愮洸椹磋伜鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨勮仢姘撻鑱垫皳鑱圭瘬"""
    if not VENV_DIR.exists():
        print("鑺掕伔鑱借寕璧傝伀  鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨勮仢鐩茶祩鑱ф皳棰呰伒姘撹伖绡撹寕褰曡仸鐚倝璺皳鑱熻仮鐚┐鑱尗闅嗚仸: python scripts.py init")
        sys.exit(1)


def init():
    """鐩茶祩鑱欒寘鑱板簮姘撹仮鑱烘皳鎼傝仴姘撹仸鑱宠寘闅嗛箍鑾借伕搴愯寕褰曡仮鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨?+ 鐩叉埉鑱虹尗纰岃伋 + .env鑼傚綍?""
    # 姘撹仮鑱告皳绂勬綖鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨勮仢
    if VENV_DIR.exists():
        print("鑺掕伀棰呰寕璧傝伀  鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨勮仢姘撹矾铏忔皳棰呰伒姘撹伖?)
    else:
        print("鍐掕伡鑱版悅 姘撹仮鑱告皳绂勬綖鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨勮仢...")
        _run(f"{sys.executable} -m venv {VENV_DIR}")
        print("鑺掕伖?鐚伓鑱峰繖鑱ヨ伡鑾借仺鐐夋皳鍨勮仢姘撹仮鑱告皳绂勬綖蹇欒仮鑱皳鑱よ伡")

    # 姘撳簮鑱ｇ尗鎷㈣仧鐩叉埉鑱虹尗纰岃伋
    print("鍐掕伡鑱▌ 姘撳簮鑱ｇ尗鎷㈣仧鑼呴殕楣胯幗鑱稿簮鐩叉埉鑱虹尗纰岃伋...")
    _run(f"{_pip()} install -e '.[dev]'")
    print("鑺掕伖?鐩叉埉鑱虹尗纰岃伋姘撳簮鑱ｇ尗鎷㈣仧姘撳簮鑱﹀繖鑱㈣伂")

    # 姘撹仮鑱告皳绂勬綖 .env 蹇欒伋鑱＄洸绂勯湶
    for env_name, log_level in [("development", "DEBUG"), ("production", "INFO")]:
        env_file = BASE_DIR / f".env.{env_name}"
        if env_file.exists():
            print(f"鑺掕伀棰呰寕璧傝伀  {env_file.name} 姘撹矾铏忔皳棰呰伒姘撹伖?)
            continue
        example = BASE_DIR / ".env.example"
        if example.exists():
            content = example.read_text(encoding="utf-8")
            content = content.replace("ENV=development", f"ENV={env_name}")
            content = content.replace("LOG_LEVEL=INFO", f"LOG_LEVEL={log_level}")
        else:
            content = f"ENV={env_name}\n\nDASHSCOPE_API_KEY=\nDEEPSEEK_API_KEY=\n\nLOG_LEVEL={log_level}\n"
        env_file.write_text(content, encoding="utf-8")
        print(f"鑺掕伖?姘撹矾铏忔皳鑱㈣伕姘撶?{env_file.name}鑼傚綍鑱︾尗鐐夎矾姘撻殕鑺︽皳鑱熸ゼ API Key")

    print()
    print("=" * 50)
    print("鍐掕伡鑱ㄨ仯 鑼呴殕楣胯幗鑱稿簮姘撹仮鑱烘皳鎼傝仴姘撹仸鑱虫皳搴愯仸蹇欒仮鑱寕褰曡仜")
    print()
    print("鐩茶祩鑱ョ洸璧傝仚蹇欓?")
    print("  1. 姘撻殕鑺︽皳鑱犺伓 .env.development 鐩茶祩棰呰幗鑱疯仦 API Key")
    print("  2. python scripts.py dev 姘撹伂鐐夋皳鑱ょ瘬鑼呴殕楣胯幗鑱稿簮")
    print("=" * 50)


def install():
    """姘撳簮鑱ｇ尗鎷㈣仧鑼呴殕楣胯幗鑱稿簮鐩叉埉鑱虹尗纰岃伋"""
    _ensure_venv()
    _run(f"{_pip()} install -e '.[dev]'")


def dev():
    """鐩茬妤兼皳褰曡仚姘撹伀鑱幗鑱ㄧ倝姘撳瀯鑱濈尗椹磋伂鐚殕鑱﹁寘闅嗛箍鑾借伕?""
    _ensure_venv()
    _run(f"{_python()} main.py", {"ENV": "development"})


def prod():
    """鐩茬妤艰幗鑱拌伡鐩叉綖鎼傝幗鑱ㄧ倝姘撳瀯鑱濈尗椹磋伂鐚殕鑱﹁寘闅嗛箍鑾借伕?""
    _ensure_venv()
    _run(f"{_python()} main.py", {"ENV": "production"})


COMMANDS = {
    "init": init,
    "dev": dev,
    "prod": prod,
    "install": install,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("姘撹伀鐐夎幗鑱扮瘬姘撹伃闄嗙洸绂勯檱:")
        for name, fn in COMMANDS.items():
            print(f"  {name:12s} - {fn.__doc__}")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
