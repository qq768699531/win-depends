from setuptools import setup, find_packages

setup(
    name="win_depends",
    version="0.1.5.2",
    description="Windows DLL/EXE dependency tree and graph tool",
    author="Vorga",
    license="MIT",
    packages=find_packages(),
    entry_points={
        "console_scripts": ["win_depends=win_depends.cli:main"],
    },
    python_requires=">=3.6",
    install_requires=[
        "tqdm>=4.64.1",  # 进度条库（可选）
        "pefile>=2024.5.17",  # PE文件解析库
    ],
)
