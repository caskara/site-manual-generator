"""CLI 主模块。

可以通过 `python -m site_manual_generator.cli.main` 直接运行。
"""
from . import app, main

__all__ = ["app", "main"]

if __name__ == "__main__":
    main()
