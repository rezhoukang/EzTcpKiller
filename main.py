"""
EzTcpKiller — TCP 端口进程查看 & 终止工具
可视化操作：查看 TCP 端口进程（支持搜索端口），一键终止占用进程
技术栈：Python + tkinter + netstat（零第三方依赖）
"""

import tkinter
from tkinter import (
    Tk, Frame, Label, Entry, Button, Scrollbar, Checkbutton,
    messagebox, StringVar, BooleanVar,
    END, VERTICAL, HORIZONTAL,
    BOTH, LEFT, RIGHT, TOP, BOTTOM, X, Y, W, E, N, S,
)
from tkinter import ttk

from core import get_tcp_connections, kill_process_by_pid


# ============================================================
# GUI 主界面
# ============================================================
class EzTcpKillerApp:
    """EzTcpKiller 主窗口应用"""

    # 状态码颜色映射
    STATUS_COLORS = {
        'LISTENING':   '#2e7d32',
        'ESTABLISHED': '#1565c0',
        'TIME_WAIT':   '#6a1b9a',
        'CLOSE_WAIT':  '#e65100',
        'SYN_SENT':    '#00838f',
    }

    def __init__(self, root):
        self.root = root
        self.root.title("EzTcpKiller — TCP 端口管理工具")
        self.root.geometry("1000x620")
        self.root.minsize(800, 480)

        # 数据缓存
        self.all_connections = []
        self.filtered_connections = []

        # 勾选状态: {tree_item_id: BooleanVar}
        self.check_vars = {}
        # 全选变量
        self.select_all_var = BooleanVar(value=False)

        # 构建界面
        self._build_menu()
        self._build_toolbar()
        self._build_table()
        self._build_statusbar()

        # 初始加载
        self.root.after(100, self.refresh_data)

    # --------------------------------------------------------
    # 菜单栏（精简：仅文件菜单，帮助占位注释留空）
    # --------------------------------------------------------
    def _build_menu(self):
        menubar = tkinter.Menu(self.root)
        file_menu = tkinter.Menu(menubar, tearoff=0)
        file_menu.add_command(label="刷新", command=self.refresh_data, accelerator="F5")
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit, accelerator="Alt+F4")
        menubar.add_cascade(label="文件", menu=file_menu)
        # 帮助菜单
        help_menu = tkinter.Menu(menubar, tearoff=0)
        help_menu.add_command(label="TCP 状态说明", command=self._show_status_help)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.root.config(menu=menubar)

    # --------------------------------------------------------
    # 工具栏：搜索 + 内嵌清除按钮 | 终止 + 复制选中信息
    # --------------------------------------------------------
    def _build_toolbar(self):
        toolbar = Frame(self.root, padx=10, pady=8)
        toolbar.pack(side=TOP, fill=X)

        # --- 左侧：搜索 ---
        Label(toolbar, text="搜索端口 (精确/范围 如 3000-3010)：",
              font=("Microsoft YaHei UI", 10)).pack(side=LEFT, padx=(0, 4))

        # 搜索框 + 内嵌清除按钮（Frame 模拟复合输入框）
        self.search_wrapper = Frame(
            toolbar, relief="solid", borderwidth=1, bg="white"
        )
        self.search_wrapper.pack(side=LEFT, padx=(0, 20))

        self.search_var = StringVar()
        self.search_var.trace_add('write', self._on_search_change)
        self.search_entry = Entry(
            self.search_wrapper, textvariable=self.search_var, width=16,
            font=("Consolas", 11), relief="flat", borderwidth=0,
            highlightthickness=0
        )
        self.search_entry.pack(side=LEFT, padx=(4, 0), pady=2)
        self.search_entry.bind('<Return>', lambda e: self._apply_filter())

        # 内嵌清除按钮（仅输入非空时显示）
        self.clear_btn = Button(
            self.search_wrapper, text="✕", command=self._clear_search,
            font=("Microsoft YaHei UI", 9), fg="#999", bg="white",
            relief="flat", borderwidth=0, padx=4, pady=0,
            activebackground="#e0e0e0", cursor="hand2"
        )

        # --- 右侧：操作按钮 ---
        Button(
            toolbar, text="复制选中信息", command=self._copy_selected_info,
            font=("Microsoft YaHei UI", 9), padx=10, cursor="hand2"
        ).pack(side=RIGHT, padx=(5, 0))

        self.kill_btn = Button(
            toolbar, text="终止", command=self.kill_checked,
            font=("Microsoft YaHei UI", 9, "bold"), padx=14,
            bg="#d32f2f", fg="white", activebackground="#b71c1c",
            activeforeground="white", cursor="hand2"
        )
        self.kill_btn.pack(side=RIGHT, padx=5)

    def _on_search_change(self, *args):
        """搜索文本变化：实时过滤 + 控制清除按钮显隐"""
        text = self.search_var.get()
        if text:
            self.clear_btn.pack(side=LEFT, padx=(0, 2), pady=2)
        else:
            self.clear_btn.pack_forget()
        self._apply_filter()

    # --------------------------------------------------------
    # 表格区域：全选框 + Treeview（含复选框列）
    # --------------------------------------------------------
    def _build_table(self):
        table_frame = Frame(self.root, padx=10, pady=4)
        table_frame.pack(side=TOP, fill=BOTH, expand=True)

        # 全选复选框（表格上方）
        select_all_frame = Frame(table_frame)
        select_all_frame.pack(side=TOP, fill=X, pady=(0, 2))
        self.select_all_cb = Checkbutton(
            select_all_frame, text="全选",
            variable=self.select_all_var,
            command=self._toggle_select_all,
            font=("Microsoft YaHei UI", 9)
        )
        self.select_all_cb.pack(side=LEFT)

        # 树+滚动条放在子 Frame 中用 grid 布局
        tree_area = Frame(table_frame)
        tree_area.pack(side=TOP, fill=BOTH, expand=True)

        columns = ('check', 'local_port', 'local_addr', 'remote_addr', 'status', 'pid', 'name')
        self.tree = ttk.Treeview(
            tree_area, columns=columns, show='headings',
            selectmode='none', height=16
        )

        col_config = [
            ('check',       '',        30, 'center'),
            ('local_port',  '本地端口', 85, 'center'),
            ('local_addr',  '本地地址', 170, 'w'),
            ('remote_addr', '远程地址', 190, 'w'),
            ('status',      '状态',     100, 'center'),
            ('pid',         'PID',      65, 'center'),
            ('name',        '进程名称', 250, 'w'),
        ]
        for col_id, text, width, anchor in col_config:
            self.tree.heading(col_id, text=text,
                              command=lambda c=col_id: self._sort_by_column(c))
            self.tree.column(col_id, width=width, anchor=anchor, minwidth=30)

        # 绑定复选框列点击
        self.tree.bind('<ButtonRelease-1>', self._on_tree_click)

        vsb = Scrollbar(tree_area, orient=VERTICAL, command=self.tree.yview)
        hsb = Scrollbar(tree_area, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky=N+S+E+W)
        vsb.grid(row=0, column=1, sticky=N+S)
        hsb.grid(row=1, column=0, sticky=E+W)

        tree_area.grid_rowconfigure(0, weight=1)
        tree_area.grid_columnconfigure(0, weight=1)

        # 快捷键
        self.root.bind('<F5>', lambda e: self.refresh_data())

    def _on_tree_click(self, event):
        """点击复选框列时切换勾选状态"""
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col = self.tree.identify_column(event.x)
        if col != '#1':
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self._toggle_item(item)

    def _toggle_item(self, item):
        """切换单行勾选"""
        var = self.check_vars.get(item)
        if var is None:
            return
        var.set(not var.get())
        self._update_check_display(item)
        self._sync_select_all()

    def _update_check_display(self, item):
        """更新行首复选框文字"""
        var = self.check_vars.get(item)
        if var is None:
            return
        mark = '\u2611' if var.get() else '\u2610'
        values = list(self.tree.item(item, 'values'))
        if values:
            values[0] = mark
            self.tree.item(item, values=values)

    def _toggle_select_all(self):
        """全选 / 取消全选"""
        state = self.select_all_var.get()
        for item in self.tree.get_children():
            var = self.check_vars.get(item)
            if var is not None:
                var.set(state)
                self._update_check_display(item)

    def _sync_select_all(self):
        """根据各行勾选状态同步全选框"""
        children = self.tree.get_children()
        if not children:
            return
        all_checked = all(
            self.check_vars.get(item, BooleanVar(value=False)).get()
            for item in children
        )
        self.select_all_var.set(all_checked)

    # --------------------------------------------------------
    # 状态栏
    # --------------------------------------------------------
    def _build_statusbar(self):
        status_frame = Frame(self.root, padx=10, pady=4)
        status_frame.pack(side=BOTTOM, fill=X)

        ttk.Separator(status_frame, orient='horizontal').pack(fill=X, pady=(0, 4))

        self.status_label = Label(
            status_frame, text="就绪", anchor=W,
            font=("Microsoft YaHei UI", 9), fg="#616161"
        )
        self.status_label.pack(side=LEFT)

        self.count_label = Label(
            status_frame, text="", anchor=E,
            font=("Microsoft YaHei UI", 9), fg="#757575"
        )
        self.count_label.pack(side=RIGHT)

    # --------------------------------------------------------
    # 数据刷新 & 过滤
    # --------------------------------------------------------
    def refresh_data(self):
        """刷新连接列表数据"""
        self.status_label.config(text="正在获取 TCP 连接信息...", fg="#1565c0")
        self.root.update_idletasks()

        try:
            self.all_connections = get_tcp_connections()
        except Exception as e:
            messagebox.showerror("错误", f"获取连接信息失败：{e}")
            self.all_connections = []

        # 去重
        seen = set()
        unique = []
        for c in self.all_connections:
            key = (c['local_port'], c['pid'], c['status'])
            if key not in seen:
                seen.add(key)
                unique.append(c)
        self.all_connections = unique

        self._apply_filter()
        self.status_label.config(text="刷新完成", fg="#2e7d32")

    def _apply_filter(self):
        """根据搜索框内容过滤：精确端口 或 范围 3000-3010"""
        search_text = self.search_var.get().strip()
        if not search_text:
            self.filtered_connections = self.all_connections[:]
            self._populate_table()
            return

        # 判断是否为范围搜索（含 "-"）
        if '-' in search_text:
            parts = search_text.split('-', 1)
            try:
                port_start = int(parts[0].strip())
                port_end = int(parts[1].strip())
                self.filtered_connections = [
                    c for c in self.all_connections
                    if port_start <= c['local_port'] <= port_end
                ]
            except ValueError:
                # 解析失败回退为精确搜索
                self.filtered_connections = [
                    c for c in self.all_connections
                    if search_text == str(c['local_port'])
                ]
        else:
            # 精确端口搜索
            self.filtered_connections = [
                c for c in self.all_connections
                if search_text == str(c['local_port'])
            ]

        self._populate_table()

    def _clear_search(self):
        """清除搜索框"""
        self.search_var.set('')
        self._apply_filter()

    def _populate_table(self):
        """填充表格数据"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.check_vars.clear()

        for conn in self.filtered_connections:
            local_port = str(conn.get('local_port', ''))
            local_addr = conn.get('local_addr', '')
            remote_addr = conn.get('remote_addr', '')
            status = conn.get('status', '')
            pid = str(conn.get('pid', ''))
            name = conn.get('name', '')

            item = self.tree.insert('', END, values=(
                '\u2610', local_port, local_addr, remote_addr, status, pid, name
            ), tags=(status.lower(),) if status else ())

            self.check_vars[item] = BooleanVar(value=False)

        for status_name, color in self.STATUS_COLORS.items():
            self.tree.tag_configure(status_name.lower(), foreground=color)

        if self.search_var.get().strip():
            self.count_label.config(
                text=f"显示 {len(self.filtered_connections)} / {len(self.all_connections)} 条"
            )
        else:
            self.count_label.config(text=f"共 {len(self.all_connections)} 条连接")

        self.select_all_var.set(False)

    def _sort_by_column(self, col):
        """点击列标题排序"""
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]
        try:
            data.sort(key=lambda x: int(x[0]) if x[0].isdigit() else x[0])
        except ValueError:
            data.sort(key=lambda x: x[0])
        for idx, (_, child) in enumerate(data):
            self.tree.move(child, '', idx)

    # --------------------------------------------------------
    # 操作功能
    # --------------------------------------------------------
    def _get_checked_items(self):
        """获取所有勾选的行"""
        return [item for item, var in self.check_vars.items() if var.get()]

    def kill_checked(self):
        """终止勾选的进程"""
        checked = self._get_checked_items()
        if not checked:
            messagebox.showinfo("提示", "请先勾选要终止的连接")
            return

        targets = []
        for item in checked:
            values = self.tree.item(item, 'values')
            if len(values) >= 6:
                port = values[1]
                pid_str = values[5]
                name = values[6] if len(values) > 6 else ''
                try:
                    pid = int(pid_str)
                except ValueError:
                    continue
                if pid > 0:
                    targets.append((pid, port, name))

        if not targets:
            messagebox.showinfo("提示", "勾选项中没有有效的进程 PID")
            return

        target_desc = '\n'.join([
            f"  PID {pid} — 端口 {port} — {name}" if name
            else f"  PID {pid} — 端口 {port}"
            for pid, port, name in targets
        ])
        confirm = messagebox.askyesno(
            "确认终止进程",
            f"确定要终止以下 {len(targets)} 个进程吗？\n\n{target_desc}\n\n此操作不可撤销。",
            icon='warning'
        )
        if not confirm:
            return

        success_count = 0
        fail_msgs = []
        for pid, port, name in targets:
            ok, msg = kill_process_by_pid(pid)
            if ok:
                success_count += 1
            else:
                fail_msgs.append(msg)

        if fail_msgs:
            messagebox.showwarning(
                "操作完成",
                f"成功终止 {success_count}/{len(targets)} 个进程\n\n"
                + '\n'.join(fail_msgs)
            )
        else:
            self.status_label.config(
                text=f"已成功终止 {success_count} 个进程",
                fg="#2e7d32"
            )

        self.root.after(500, self.refresh_data)

    def _copy_selected_info(self):
        """复制勾选行的完整信息到剪贴板（Tab 分隔）"""
        checked = self._get_checked_items()
        if not checked:
            messagebox.showinfo("提示", "请先勾选要复制的连接")
            return

        lines = ['本地端口\t本地地址\t远程地址\t状态\tPID\t进程名称']
        for item in checked:
            values = self.tree.item(item, 'values')
            if len(values) >= 7:
                line = '\t'.join([
                    values[1],  # 本地端口
                    values[2],  # 本地地址
                    values[3],  # 远程地址
                    values[4],  # 状态
                    values[5],  # PID
                    values[6],  # 进程名称
                ])
                lines.append(line)

        text = '\n'.join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_label.config(
            text=f"已复制 {len(lines)} 条信息到剪贴板",
            fg="#2e7d32"
        )

    def _show_status_help(self):
        """显示 TCP 状态说明"""
        messagebox.showinfo(
            "TCP 状态说明",
            "LISTENING      监听中 — 端口已开放，等待外部连接\n"
            "ESTABLISHED    已建立 — 正在活跃通信中\n"
            "TIME_WAIT      等待 — 连接已关闭，残留等待（无关联进程）\n"
            "CLOSE_WAIT     等待关闭 — 远端已断开，本端尚未关闭\n"
            "FIN_WAIT       等待断开 — 正在执行断开握手\n"
            "SYN_SENT       发送中 — 正在发起连接请求\n"
            "CLOSING        关闭中 — 双方同时关闭\n"
            "LAST_ACK       最后确认 — 等待最终确认包\n"
        )


# ============================================================
# 程序入口
# ============================================================
def main():
    root = Tk()
    EzTcpKillerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
