# 打包说明

## 安装依赖

```bash
uv pip install pyinstaller
```

或者安装所有开发依赖：

```bash
uv pip install -e ".[dev]"
```

## 打包步骤

### macOS arm64

在 macOS arm64 系统上运行：

```bash
python build.py
```

或者直接使用 PyInstaller：

```bash
pyinstaller --onefile --name douban-comment --clean --noconfirm main.py
```

### Windows x64

在 Windows x64 系统上运行：

```bash
python build.py
```

或者直接使用 PyInstaller：

```bash
pyinstaller --onefile --name douban-comment --clean --noconfirm main.py
```

## 输出

打包后的可执行文件位于：

- macOS: `dist/macos-arm64/douban-comment` 或 `dist/macos-x64/douban-comment`
- Windows: `dist/windows-x64/douban-comment.exe`

## 使用

打包后的可执行文件可以直接运行：

```bash
# macOS/Linux
./douban-comment <subject-id>

# Windows
douban-comment.exe <subject-id>
```

## 注意事项

1. 打包时需要确保所有依赖都已安装
2. 打包后的文件会比较大（通常 20-50MB），因为包含了 Python 解释器和所有依赖
3. 首次运行可能需要一些时间解压文件
4. 确保 `.env` 文件与可执行文件在同一目录，或使用绝对路径
