"""保留旧版调用入口，引导到当前的并排安装流程。"""


def arrange():
    raise RuntimeError('旧安装整理器已停用。请按发布检查单在新目录构建并验证副本，然后切换快捷方式。')


if __name__ == '__main__':
    try:
        arrange()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None
