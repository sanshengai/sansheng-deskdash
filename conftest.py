# 仓根 conftest — 把 scripts/ 加进 sys.path,测试里统一 `from lib.xxx import ...`
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
