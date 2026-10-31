"""把调用者同一协作截止显式带入有界计算单元；不持有全局时钟或状态。"""


def checked(values, check=None, *, interval=1):
    """独立helper默认原迭代语义；有预算时按指定单元检查并在结束时复核。

    外层历史/日帧逐项检查，精确数值及编码小步每32项检查。调用者必须
    保证单项及interval有界；单次Python/C运算仍由宿主调度完成。
    """
    if check is None:
        yield from values
        return
    for index, value in enumerate(values):
        if index % interval == 0:
            check()
        yield value
    check()
