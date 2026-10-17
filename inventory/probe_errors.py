import errno


def explain_probe(error, error_number=None):
    """Describe observed TCP failure without claiming a proven root cause."""
    if not error:
        return {"reason": "TCP 连接已建立，目标端口可达。", "suggestion": "端口可达不代表数据库账号验证或 SQL 执行成功。"}
    if error == "ConnectionRefusedError" or error_number in (errno.ECONNREFUSED, 10061):
        return {"reason": "连接被拒绝：目标没有接受这个端口的 TCP 连接。常见原因是服务未启动、监听端口填错，或防火墙主动拒绝。", "suggestion": "检查数据库服务是否启动、IP 和端口是否正确、服务是否监听该地址，再检查防火墙放行规则。"}
    if error in ("TimeoutError", "timeout") or error_number in (errno.ETIMEDOUT, 10060):
        return {"reason": "连接超时：在 3 秒内未能建立 TCP 连接。可能是网络不通、防火墙丢弃连接或目标响应过慢。", "suggestion": "检查目标主机在线状态、网络路由及防火墙规则，确认服务可用后重试。"}
    if error_number in (errno.ENETUNREACH, errno.EHOSTUNREACH, 10051, 10065):
        return {"reason": "网络或主机不可达：当前服务器无法通过网络路由到目标地址。", "suggestion": "检查 IP、网关、路由和 VPN 连接，确认两台服务器之间网络互通。"}
    if error == "PermissionError" or error_number in (errno.EACCES, errno.EPERM, 10013):
        return {"reason": "连接被本机权限或网络安全策略阻止。", "suggestion": "检查本机防火墙、终端安全软件及进程网络访问权限。"}
    if error == "ConnectionResetError" or error_number in (errno.ECONNRESET, 10054):
        return {"reason": "连接被重置：目标或中间网络设备中断了 TCP 连接。", "suggestion": "检查目标服务日志和网络设备策略，确认服务稳定后重试。"}
    return {"reason": "TCP 连接失败，仅凭此错误无法确定具体原因。", "suggestion": "核对目标 IP、端口、服务监听和网络策略，并结合原始错误类型检查服务器日志。"}
