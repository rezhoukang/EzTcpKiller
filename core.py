"""
EzTcpKiller — 数据层
纯 netstat + tasklist，零第三方依赖
"""

import subprocess
import re


def get_pid_name_map():
    """
    一次性调用 tasklist 获取所有进程的 {PID: 进程名} 映射。
    避免逐条查询导致几百次子进程调用卡死 UI。
    """
    pid_map = {}
    try:
        output = subprocess.check_output(
            ['tasklist', '/FO', 'CSV', '/NH'],
            timeout=10, encoding='gbk', errors='replace'
        )
        # tasklist /FO CSV 输出格式: "进程名.exe","1234","Console","1","123,456 K"
        for line in output.splitlines():
            parts = line.split(',')
            if len(parts) >= 2:
                name = parts[0].strip('"')
                pid_str = parts[1].strip('"')
                try:
                    pid_map[int(pid_str)] = name
                except ValueError:
                    pass
    except Exception:
        pass
    return pid_map


def get_tcp_connections():
    """
    通过解析 netstat -ano + 一次性 tasklist 获取所有 TCP 连接信息。
    返回: list[dict]，每项包含 local_port, local_addr, remote_addr, remote_port, status, pid, name
    """
    # 先一次性获取所有进程名映射（仅 1 次子进程调用）
    pid_map = get_pid_name_map()

    results = []
    try:
        output = subprocess.check_output(
            ['netstat', '-ano'], stderr=subprocess.STDOUT, timeout=10,
            encoding='gbk', errors='replace'
        )
    except Exception:
        return results

    # 匹配行示例: TCP    0.0.0.0:135    0.0.0.0:0    LISTENING    4
    pattern = re.compile(
        r'^\s*TCP\s+'
        r'(?P<local>[^\s]+)\s+'
        r'(?P<remote>[^\s]+)\s+'
        r'(?P<status>\w+)\s+'
        r'(?P<pid>\d+)\s*$'
    )

    for line in output.splitlines():
        m = pattern.match(line)
        if not m:
            continue

        local = m.group('local')
        remote = m.group('remote')
        status = m.group('status')
        pid = int(m.group('pid'))

        # 解析本地端口
        local_port = 0
        if ':' in local:
            try:
                local_port = int(local.rsplit(':', 1)[-1])
            except ValueError:
                pass

        # 解析远程端口
        remote_port = ''
        if ':' in remote:
            try:
                remote_port = int(remote.rsplit(':', 1)[-1])
            except ValueError:
                pass

        # 从预建映射表中 O(1) 查进程名（不再逐条调 tasklist）
        name = pid_map.get(pid, '') if pid else ''

        results.append({
            'local_addr': local,
            'local_port': local_port,
            'remote_addr': remote,
            'remote_port': remote_port,
            'status': status,
            'pid': pid,
            'name': name,
        })

    return results


def kill_process_by_pid(pid):
    """
    通过 taskkill 终止指定 PID 的进程。
    返回: (success: bool, message: str)
    """
    try:
        result = subprocess.run(
            ['taskkill', '/F', '/PID', str(pid)],
            capture_output=True, timeout=10,
            encoding='gbk', errors='replace'
        )
        if result.returncode == 0:
            return True, f"已终止进程 (PID: {pid})"
        else:
            err = result.stderr.strip() or result.stdout.strip()
            if '没有找到' in err or 'not found' in err.lower():
                return True, f"进程 (PID: {pid}) 已不存在"
            return False, f"终止失败 (PID: {pid})：{err}"
    except Exception as e:
        return False, f"终止进程 (PID: {pid}) 失败：{e}"
