#!/usr/bin/env python3
"""打包脚本：将程序打包为单个可执行文件"""

import platform
import subprocess
import sys


def get_platform_info():
    """获取平台信息并返回标准化的平台标识"""
    system = platform.system()
    machine = platform.machine().lower()

    # 标准化架构名称
    arch_map = {
        "x86_64": "x64",
        "amd64": "x64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "arm32",
        "armv8l": "arm64",
        "i386": "x86",
        "i686": "x86",
    }

    arch = arch_map.get(machine, machine)

    # 标准化系统名称
    system_map = {
        "Darwin": "macos",
        "Windows": "windows",
        "Linux": "linux",
    }

    system_name = system_map.get(system, system.lower())

    return system_name, arch, system, machine


def build_executable():
    """根据当前平台构建可执行文件"""
    system_name, arch, system, machine = get_platform_info()

    print(f"当前平台: {system} ({machine})")
    print(f"标准化标识: {system_name}-{arch}")

    # 检查 PyInstaller 是否安装
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("错误: PyInstaller 未安装")
        print("请运行: uv pip install pyinstaller")
        sys.exit(1)

    # 构建 PyInstaller 命令
    cmd = [
        "pyinstaller",
        "--onefile",  # 打包为单个文件
        "--name",
        "douban-comment",  # 可执行文件名
        "--clean",  # 清理临时文件
        "--noconfirm",  # 不询问确认
        "main.py",
    ]

    # 根据平台和架构设置输出目录（支持所有平台和架构）
    output_dir = f"dist/{system_name}-{arch}"
    print(f"构建 {system_name} {arch} 版本...")

    cmd.extend(["--distpath", output_dir])

    # 添加隐藏导入（如果需要）
    hidden_imports = [
        "bs4",
        "dotenv",
        "requests",
    ]
    for module in hidden_imports:
        cmd.extend(["--hidden-import", module])

    # 执行打包
    print(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        print(f"\n✅ 打包成功！可执行文件位于: {output_dir}/")
        if system == "Windows":
            exe_name = "douban-comment.exe"
        else:
            exe_name = "douban-comment"
        print(f"   文件: {output_dir}/{exe_name}")
        print(f"   平台: {system_name}-{arch}")
    else:
        print("\n❌ 打包失败")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()
