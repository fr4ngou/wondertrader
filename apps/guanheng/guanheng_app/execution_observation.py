"""消费原CTA发布的业务结果；金融事实和执行状态保持各原owner所有。"""
from .execution_process import ManagedPythonExecutionProcess, _RETAINED_PYTHON_PACKAGES
from .managed_local_process import _json, _read, _require
from .strategy_runtime_projection import project_strategy



class ObservedPythonExecutionProcess(ManagedPythonExecutionProcess):
    """原监督者的只读消费hook；不改变启动、停止、恢复及原桥发布。"""

    def observe_strategy(self, deadline):
        """有界读池调用，使用原绝对单调截止；读取期间不持生命周期锁。"""
        with self._condition:
            if self.config is None or self.config.packages != _RETAINED_PYTHON_PACKAGES:
                return dict(state='unconfigured', strategy=None)
            identity = self._control_id, self._host_pid, self.config.configuration_sha256
            directory = self._directory
            _require(self.status()['ready'] and identity[1] is not None)
        ready = self._receipt('ready.json', deadline)
        _require(ready['pid'] == identity[1])
        try:
            raw = _read(directory / 'strategies.json', 4 * 1024 * 1024, clock=self._clock, deadline=deadline)
        except FileNotFoundError:
            result = dict(state='waiting', strategy=None)
        else:
            projected = project_strategy(_json(raw))
            result = dict(state='available' if projected else 'waiting', strategy=projected)
        with self._condition:
            _require(identity == (self._control_id, self._host_pid, self.config.configuration_sha256)
                     and directory == self._directory and self.status()['ready'])
        self._check(deadline)
        return result
