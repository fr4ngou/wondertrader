"""后台构建工具的统一进程创建选项；调用方继续拥有Job、等待和日志。"""
import os
import subprocess


def background_process_options(*, suspended=False, private_console=False):
    """后台直连命令无控制台；构建driver的私有隐藏控制台供第三方后代继承。

    NO_WINDOW不传给后代。已在隐藏控制台中的工具保留该控制台，使Ninja等
    使用普通CreateProcess的后代也保持隐藏；可见终端中的命令仍单独NO_WINDOW。
    """
    if os.name != "nt":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    if private_console:
        flags = subprocess.CREATE_NEW_CONSOLE
    else:
        import ctypes as C
        kernel = C.WinDLL("kernel32", use_last_error=True)
        kernel.GetConsoleWindow.restype = C.c_void_p
        window = kernel.GetConsoleWindow()
        user = C.WinDLL("user32", use_last_error=True)
        user.IsWindowVisible.argtypes = (C.c_void_p,)
        user.IsWindowVisible.restype = C.c_int
        flags = 0 if window and not user.IsWindowVisible(window) else subprocess.CREATE_NO_WINDOW
    return {"startupinfo": startup,
            "creationflags": flags | (0x4 if suspended else 0)}


