"""
DeepSeek Monitor - 安装脚本
由 setup.bat 调用，需要 Python 标准库即可运行
"""
import os
import sys
import subprocess
import tempfile


def run_cmd(cmd, desc=""):
    """运行命令并检查结果"""
    print(f"  {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=False)
    return result.returncode == 0


def check_python():
    """检查 Python 版本"""
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 8):
        print("❌ 需要 Python 3.8 或更高版本！")
        sys.exit(1)
    print(f"✅ Python {v.major}.{v.minor}.{v.micro}")


def install_deps():
    """安装依赖包"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    req = os.path.join(script_dir, "requirements.txt")

    print("\n安装依赖包...")
    # 先尝试清华源
    ok = run_cmd(
        f'pip install -r "{req}" -i https://pypi.tuna.tsinghua.edu.cn/simple',
        "pip install (tsinghua mirror)",
    )
    if not ok:
        # 回退到默认源
        ok = run_cmd(f'pip install -r "{req}"', "pip install (default)")
    if ok:
        print("✅ 依赖安装完成")
    else:
        print("❌ 依赖安装失败，请检查网络连接")
        sys.exit(1)


def create_shortcut(target_path, shortcut_path, working_dir, description="DeepSeek Monitor"):
    """通过 VBScript 创建 Windows 快捷方式"""
    vbs = f'''
Set ws = WScript.CreateObject("WScript.Shell")
Set sc = ws.CreateShortcut("{shortcut_path}")
sc.TargetPath = "pythonw.exe"
sc.Arguments = """{target_path}"""
sc.WorkingDirectory = "{working_dir}"
sc.Description = "{description}"
sc.Save
'''
    # 写入临时 vbs 文件
    fd, vbs_path = tempfile.mkstemp(suffix=".vbs", prefix="dsm_")
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(vbs)

    try:
        result = subprocess.run(
            ["cscript", "//nologo", vbs_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True
        else:
            print(f"  VBScript error: {result.stderr}")
            return False
    except Exception as e:
        print(f"  创建快捷方式失败: {e}")
        return False
    finally:
        try:
            os.unlink(vbs_path)
        except OSError:
            pass


def get_desktop():
    """获取桌面路径"""
    import ctypes
    from ctypes import wintypes
    try:
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf)  # CSIDL_DESKTOP = 0
        return buf.value
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Desktop")


def get_startup():
    """获取启动文件夹路径"""
    import ctypes
    from ctypes import wintypes
    try:
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 7, None, 0, buf)  # CSIDL_STARTUP = 7
        return buf.value
    except Exception:
        return ""


def setup_shortcuts():
    """创建桌面和启动文件夹快捷方式"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(script_dir, "run.py")

    # 桌面快捷方式
    desktop = get_desktop()
    shortcut_path = os.path.join(desktop, "DeepSeek Monitor.lnk")
    print(f"\n创建桌面快捷方式...")
    if create_shortcut(target, shortcut_path, script_dir):
        print(f"✅ {shortcut_path}")

    # 启动文件夹
    startup = get_startup()
    if startup:
        choice = input("\n是否开机自动启动？(y/N): ").strip().lower()
        if choice in ("y", "yes"):
            startup_path = os.path.join(startup, "DeepSeek Monitor.lnk")
            if create_shortcut(target, startup_path, script_dir):
                print(f"✅ 已添加开机自启")
    else:
        print("⚠️  无法获取启动文件夹路径，跳过开机自启设置")


def main():
    print("=" * 50)
    print("  DeepSeek Monitor - 安装程序")
    print("=" * 50)

    check_python()
    install_deps()
    setup_shortcuts()

    print()
    print("=" * 50)
    print("  🎉 安装完成！")
    print()
    print("  双击桌面「DeepSeek Monitor」图标启动")
    print("  首次运行会要求设置 API Key")
    print("=" * 50)
    print()
    input("按回车键退出...")


if __name__ == "__main__":
    main()
