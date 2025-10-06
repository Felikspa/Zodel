"""
应用程序的主入口点。

运行此文件将启动 Gradio Web 服务。
"""

from app.ui import GradioApp

if __name__ == "__main__":
    app_instance = GradioApp()
    app_ui = app_instance.build()

    # 启动 Gradio 服务
    # debug=True 可以在代码更改时自动重载，方便开发
    # share=True 会创建一个公开链接，方便分享
    app_ui.launch(debug=True,share=False)