# tests/test_validate_module.py — validate_module.py 校验门的测试:
#   ① 六个官方模块跑 validate 全绿(clock-calendar/todo 走完整 dry-run;四个联网模块走静态
#      --no-dry-run,避开 pytest 里的慢/抖动网络,静态项已足以证明绿灯);
#   ② new_module 生成的骨架直接过 validate(含 dry-run)且能装配过布局不变量;
#   ③ 故意造的坏模块各报对应错:未声明域名 / eval / schema 用 oneOf / 输出不过 schema。
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "scripts"))
sys.path.insert(0, os.path.join(_REPO, "scripts", "lib"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import new_module                                   # noqa: E402
import validate_module as vm                        # noqa: E402

_MODROOT = os.path.join(_REPO, "modules")

# 联网模块用静态校验(dry-run 会真跑 ping/http,慢且抖);离线确定的两个走完整 dry-run。
_OFFLINE_DRYRUN = ["clock-calendar", "todo"]
_STATIC_ONLY = ["weather", "github", "net-latency", "server-status"]


# ============================================================
#  ① 六个官方模块全绿
# ============================================================

@pytest.mark.parametrize("mid", _OFFLINE_DRYRUN)
def test_official_offline_modules_green_with_dryrun(mid):
    rep = vm.validate_module(os.path.join(_MODROOT, mid), dry_run=True)
    assert rep.ok, "%s 应绿灯,errors=%s" % (mid, rep.errors)
    # dry-run 真跑过且输出过 output.schema
    assert rep.dry_run is not None and rep.dry_run.get("schema_ok") is True


@pytest.mark.parametrize("mid", _STATIC_ONLY)
def test_official_network_modules_green_static(mid):
    rep = vm.validate_module(os.path.join(_MODROOT, mid), dry_run=False)
    assert rep.ok, "%s 应绿灯,errors=%s" % (mid, rep.errors)


def test_github_gh_binary_backed_note():
    """github 调 gh 二进制被标 network-opaque,且 gh→api.github.com 已在 privacy.network 背书(note 非 warning)。"""
    rep = vm.validate_module(os.path.join(_MODROOT, "github"), dry_run=False)
    assert rep.ok and rep.network_opaque
    assert any("gh" in n and "背书" in n for n in rep.notes)
    assert not rep.warnings, rep.warnings


def test_weather_url_domains_subset_declared():
    """weather 的 URL 字面量域名全部在 privacy.network 声明内。"""
    rep = vm.validate_module(os.path.join(_MODROOT, "weather"), dry_run=False)
    assert rep.ok
    assert rep.url_domains and rep.url_domains <= set(rep.declared_net)


# ============================================================
#  ② new_module 骨架过 validate + 能装配过布局
# ============================================================

def test_new_module_skeleton_passes_validate(tmp_path):
    target, prefix, _ = new_module.generate("demo", str(tmp_path), force=True)
    assert prefix == "Demo"
    rep = vm.validate_module(target, dry_run=True)
    assert rep.ok, rep.errors
    assert rep.dry_run.get("schema_ok") is True         # 骨架桩输出过 output.schema
    assert any("骨架桩" in n for n in rep.notes)          # 且给出"还是骨架桩"的人话提示


def test_new_module_prefix_derivation():
    assert new_module.derive_prefix("my-nas-space") == "MyNasSpace"
    assert new_module.derive_prefix("weather") == "Weather"


def test_new_module_skeleton_assembles_and_layout(tmp_path):
    """骨架 band.inc 装配后过四布局不变量(证明新模块开箱能上墙)。"""
    import assemble as asm
    from test_layout import check_all
    board = tmp_path / "board"
    board.mkdir()
    new_module.generate("demo", str(board), force=True)
    res = asm.assemble(str(board), ["demo"], size="M")
    bad = {k: v for k, v in check_all(res["ini_text"]).items() if v}
    assert not bad, bad


# ============================================================
#  ③ 坏模块各报对应错
# ============================================================

def _scaffold(tmp_path, mid):
    target, _, _ = new_module.generate(mid, str(tmp_path), force=True)
    return target


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def test_bad_undeclared_domain(tmp_path):
    """collector 出现未在 privacy.network 声明的 URL 字面量 → 报域名不一致。"""
    d = _scaffold(tmp_path, "baddomain")
    _write(os.path.join(d, "collector.py"),
           "import json, sys\n"
           "URL = 'https://evil.example.com/data'   # 未声明的域名\n"
           "def main():\n"
           "    sys.stdout.buffer.write(json.dumps({'Title':'x','Status':'y'}).encode()+b'\\n')\n"
           "main()\n")
    rep = vm.validate_module(d, dry_run=False)
    assert not rep.ok
    assert any("evil.example.com" in e and "privacy.network" in e for e in rep.errors), rep.errors


def test_bad_eval_call(tmp_path):
    """collector 用 eval() → 报禁用调用。"""
    d = _scaffold(tmp_path, "badeval")
    _write(os.path.join(d, "collector.py"),
           "import json, sys\n"
           "def main():\n"
           "    _ = eval('1+1')\n"
           "    sys.stdout.buffer.write(json.dumps({'Title':'x','Status':'y'}).encode()+b'\\n')\n"
           "main()\n")
    rep = vm.validate_module(d, dry_run=False)
    assert not rep.ok
    assert any("eval" in e for e in rep.errors), rep.errors


def test_bad_schema_unsupported_keyword(tmp_path):
    """output.schema 用了校验器不支持的 oneOf → 报"假信心"。"""
    d = _scaffold(tmp_path, "badschema")
    _write(os.path.join(d, "output.schema.json"),
           '{\n'
           '  "$schema": "https://json-schema.org/draft/2020-12/schema",\n'
           '  "type": "object",\n'
           '  "required": ["Title", "Status"],\n'
           '  "properties": {"Title": {"type": "string"}, "Status": {"type": "string"}},\n'
           '  "oneOf": [{"required": ["Title"]}],\n'
           '  "additionalProperties": false\n'
           '}\n')
    rep = vm.validate_module(d, dry_run=False)
    assert not rep.ok
    assert any("oneOf" in e for e in rep.errors), rep.errors


def test_bad_output_fails_schema(tmp_path):
    """collector 输出多出 schema 未声明的键(additionalProperties:false)→ dry-run 报不过 output.schema。"""
    d = _scaffold(tmp_path, "badoutput")
    _write(os.path.join(d, "collector.py"),
           "import json, sys\n"
           "def main():\n"
           "    out = {'Title':'x','Status':'y','Extra':'z'}   # Extra 不在 schema\n"
           "    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode('utf-8')+b'\\n')\n"
           "main()\n")
    rep = vm.validate_module(d, dry_run=True)
    assert not rep.ok
    assert any("output.schema" in e for e in rep.errors), rep.errors


def test_bad_shell_true(tmp_path):
    """collector 用 subprocess shell=True → 报硬红线。"""
    d = _scaffold(tmp_path, "badshell")
    _write(os.path.join(d, "collector.py"),
           "import json, subprocess, sys\n"
           "def main():\n"
           "    subprocess.run('echo hi', shell=True)\n"
           "    sys.stdout.buffer.write(json.dumps({'Title':'x','Status':'y'}).encode()+b'\\n')\n"
           "main()\n")
    rep = vm.validate_module(d, dry_run=False)
    assert not rep.ok
    assert any("shell=True" in e for e in rep.errors), rep.errors
