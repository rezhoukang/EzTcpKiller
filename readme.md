通过终端命令和可视化窗口交互
达到可视化操作：
查看tcp端口进程（支持搜索端口）
删除tcp端口进程

技术栈
底层原理
Python代码无法双击直接运行，打包 = Python解释器 + 项目代码 + 第三方依赖 合并封装为exe
选用PyInstaller

1.先安装
pip install pyinstaller
2.打包为GUI软件
关闭黑框、单文件exe、自定义图标
pyinstaller -F -w -i 图标.ico main.py
参数释义
-F ：打包为单个exe绿色文件（推荐）
-w ：隐藏cmd黑色控制台窗口（图形界面必须加）
-i ：设置桌面软件图标
禁止全局环境打包：新建虚拟venv环境，只装项目依赖，体积直接减半
