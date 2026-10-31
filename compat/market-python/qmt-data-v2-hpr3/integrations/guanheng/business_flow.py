"""原 Portfolio/Bridge 的薄调用边界；目标、审批、签名分别保留原 owner。"""
from __future__ import annotations

from dataclasses import dataclass

from .broker import SignedCommand


@dataclass(frozen=True)
class RetainedEvaluation:
    result: object
    signing_allowed: bool
    reason: str


class RetainedBusinessFlow:
    """依赖 ExternalQmt.retained() 的原函数，不把 shadow 评估转换为审批。

    当前 evaluate_portfolio 固定返回 shadow 禁执行；该结果保持原义。
    sign_reserved_development 只接收另一路原风险政策已经确认的合成 reservation/queue/terms。
    store、signer 都由原 Bridge owner 提供，本门面不创建账户账本或保管生产密钥。
    """

    def __init__(self, modules):
        self.modules = modules

    def evaluate(self, request):
        request = self.modules["risk"].PortfolioRequest.model_validate(request)
        result = self.modules["risk"].evaluate_portfolio(request)
        # 原服务当前的 shadow 拒绝不会被门面提升为可签名审批。
        return RetainedEvaluation(result, False, "原 Portfolio shadow 结果只提供风险/目标，不授命令审批")

    def sign_reserved_development(self, *, risk_plan, approval_terms, queue_items,
                                  occurred_at, command_store, signer):
        """复用原协调审批→命令构造→Bridge提交签名，资源与幂等仍属于原 command_store。

        此接口不接受 StrategyIntent 代替 risk_plan；调用者须提供已有审批链冻结事实。
        返回含原签名 bytes 的投递输入；Host 缺少命令资格时继续由 Broker 门面拒绝。
        """
        if type(command_store) is not self.modules["command_store"].InMemoryCommandStore:
            raise ValueError("隔离候选只使用原参考内存 store；生产签名须走原协调事务")
        if any(item.account_environment != "simulation" for item in risk_plan.reservations):
            raise ValueError("隔离候选仅接受合成模拟风险预留")
        approvals = self.modules["approvals"].prepare_coordinated_approvals(
            risk_plan=risk_plan, approval_terms=approval_terms, queue_items=queue_items, occurred_at=occurred_at)
        commands = self.modules["commands"].prepare_coordinated_commands(
            approvals=[item.approval for item in approvals],
            queue_items={item.approved_queue.queue_item_id: item.approved_queue for item in approvals},
            occurred_at=occurred_at)
        result = []
        for approval, prepared in zip(approvals, commands):
            command_store.save_approval(approval.approval)
            signed = command_store.commit_signed_command(prepared.command, signer)
            body = self.modules["contracts"].OrderCommand.model_validate(signed).model_dump_json().encode("utf-8")
            result.append((approval.approval, signed, SignedCommand.validate(body, self.modules["contracts"].OrderCommand)))
        return tuple(result)

    def sign_authorized_approval(self, *, approval, repository, command_store, signer, occurred_at,
                                common_trading_date_provider=None):
        """已有审批的正式接缝；完全委托原 Bridge 协调事务，不自行保存审批或队列。"""
        return self.modules["commands"].commit_coordinated_command_for_approval(
            approval=approval, repository=repository, command_store=command_store, signer=signer,
            occurred_at=occurred_at, common_trading_date_provider=common_trading_date_provider)
