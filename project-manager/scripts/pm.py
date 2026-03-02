#!/usr/bin/env python3
import os
import sys
import json
import argparse
import subprocess

CONFIG_FILE = os.path.expanduser("~/.pm_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def add_project(name, description):
    config = load_config()
    current_dir = os.getcwd()
    config[name] = {
        "path": current_dir,
        "desc": description or "No description"
    }
    save_config(config)
    print(f"✅ Project '{name}' registered.")
    print(f"   Path: {current_dir}")
    print(f"   Desc: {description or 'None'}")

def list_projects():
    config = load_config()
    if not config:
        print("\n📭 No projects registered yet. Use 'pm add <name> [desc]' to add one.")
        return
    
    print("\n" + "="*70)
    print(f"{'ALIAS':<15} {'DESCRIPTION':<30} {'PATH'}")
    print("-" * 70)
    for name, info in config.items():
        desc = info.get('desc', 'No description')
        path = info.get('path', 'Unknown')
        # 截断过长的描述并处理简单对齐
        display_desc = (desc[:27] + '..') if len(desc) > 27 else desc
        print(f"{name:<15} {display_desc:<30} {path}")
    print("="*70 + "\n")

def is_running_in_warp():
    """检测当前是否在 Warp 终端中运行"""
    # 方法1: 检查 WARP_IS_LOCAL_SHELL_SESSION 环境变量
    if os.environ.get('WARP_IS_LOCAL_SHELL_SESSION') == '1':
        return True
    # 方法2: 检查 WARP_USE_SSH_WRAPPER 环境变量
    if 'WARP_USE_SSH_WRAPPER' in os.environ:
        return True
    # 方法3: 检查 TERM_PROGRAM
    if os.environ.get('TERM_PROGRAM', '').lower() == 'warp':
        return True
    # 方法4: 通过 AppleScript 检查前台应用
    try:
        result = subprocess.run(
            ['osascript', '-e', 'tell application "System Events" to name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=2
        )
        return 'warp' in result.stdout.lower()
    except:
        return False

def open_project(name, tool=None, terminal="Terminal", current=False):
    config = load_config()
    if name not in config:
        print(f"❌ Error: Project '{name}' not found.")
        return

    project_path = config[name]['path']
    if not os.path.exists(project_path):
        print(f"❌ Error: Path does not exist: {project_path}")
        return

    # Determine command based on tool
    cmd = "pm menu" # Default behavior
    if tool:
        if tool == 'gemini':
            cmd = "gemini"
        elif tool == 'opencode':
            cmd = "code ."
        elif tool == 'codex':
            cmd = "codex"
        elif tool == 'shell':
            cmd = "clear"
        elif tool == 'claude':
            cmd = "claude"
        else:
            print(f"⚠️ Unknown tool '{tool}', falling back to menu.")

    if current:
        # 在当前 tab 中直接执行
        os.chdir(project_path)
        if cmd == "pm menu":
            show_menu()
        elif cmd == "clear":
            os.system("clear")
        else:
            os.system(cmd)
        return

    if terminal.lower() == "warp":
        # 检测是否在 Warp 中运行
        in_warp = is_running_in_warp()

        full_command = f"cd {project_path} && {cmd}"

        if in_warp:
            # 在当前 Warp 窗口中新建 tab
            # 直接发送 Cmd+T 到前台应用（应该是 Warp）
            process = subprocess.Popen('pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
            process.communicate(full_command.encode('utf-8'))

            # 只使用 System Events，不激活应用，避免触发新窗口
            applescript = '''
            tell application "System Events"
                keystroke "t" using command down
                delay 0.3
                keystroke "v" using command down
                delay 0.1
                key code 36
            end tell
            '''
            subprocess.run(['osascript', '-e', applescript])
            return
        else:
            # 新启动 Warp 窗口
            process = subprocess.Popen('pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
            process.communicate(full_command.encode('utf-8'))

            script = f'''
            tell application "Warp"
                activate
                tell application "System Events"
                    keystroke "n" using command down
                    delay 0.8
                    keystroke "v" using command down
                    delay 0.2
                    key code 36
                end tell
            end tell
            '''
            subprocess.run(["osascript", "-e", script])
            return
    else:
        script = f'''
        tell application "Terminal"
            activate
            do script "cd {project_path} && {cmd}"
        end tell
        '''
        subprocess.run(["osascript", "-e", script])

def show_menu():
    current_dir_name = os.path.basename(os.getcwd())
    os.system('clear')
    
    print("\n🚀 " + "="*30)
    print(f"  Project Launcher: [{current_dir_name}]")
    print("="*33)
    print("  [1] Gemini CLI")
    print("  [2] OpenCode (VS Code)")
    print("  [3] Codex")
    print("  [4] Claude Code")
    print("  [5] Shell Only")
    print("="*33)

    try:
        choice = input("\n👉 Select a tool [1-5] (default 5): ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = '5'

    if choice == '1':
        os.system("gemini")
    elif choice == '2':
        os.system("code .")
    elif choice == '3':
        os.system("codex")
    elif choice == '4':
        os.system("claude")
    elif choice == '5' or not choice:
        print("Staying in Shell.")
    else:
        print("Invalid choice. Staying in Shell.")

class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action(self, action):
        if isinstance(action, argparse._SubParsersAction):
            # 自定义子命令的显示格式，不显示标题
            parts = []
            for name, subparser in action.choices.items():
                if name == 'menu':
                    continue
                desc = subparser.description or 'No description'
                parts.append(f"  {C.GREEN}{name:<12}{C.END}  {desc}")
            return '\n'.join(parts) + '\n'
        return super()._format_action(action)

    def _format_usage(self, usage, actions, groups, prefix):
        # 自定义 usage 显示
        if self._prog == 'pm':
            # 主命令
            if prefix is None:
                prefix = 'Usage: '
            return f"\n{C.BOLD}{C.BLUE}{prefix}{C.END}{self._prog} [COMMAND] [OPTIONS]\n"
        else:
            # 子命令：使用默认格式但不带颜色
            result = super()._format_usage(usage, actions, groups, prefix)
            # 移除所有颜色代码
            for code in [C.BOLD, C.BLUE, C.GREEN, C.CYAN, C.GRAY, C.END]:
                result = result.replace(code, '')
            return result

    def start_section(self, heading):
        # 美化 section 标题，移除冒号
        if heading == 'positional arguments':
            heading = f'{C.BOLD}{C.BLUE}Commands{C.END}'
        elif heading == 'options':
            heading = f'{C.BOLD}{C.BLUE}Options{C.END}'
        else:
            heading = heading.rstrip(':')
        super().start_section(heading)

class C:
    """ANSI 颜色代码"""
    BOLD = '\033[1m'
    GREEN = '\033[32m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'
    GRAY = '\033[90m'
    END = '\033[0m'

def create_parser():
    """创建并配置参数解析器"""

    # 构建详细的描述
    description = f"""
{C.BOLD}{C.BLUE}🚀 Project Manager - 项目快速启动工具{C.END}

管理项目路径别名，快速在新终端中打开项目，并可选择启动特定工具。"""

    # 使用示例
    examples = f"""{C.BOLD}{C.BLUE}Examples:{C.END}

  # 添加当前目录为项目
  {C.GREEN}pm add myapp "My Application"{C.END}

  # 列出所有项目
  {C.GREEN}pm list{C.END}

  # 打开项目（会显示工具选择菜单）
  {C.GREEN}pm open myapp{C.END}

  # 直接用 VS Code 打开项目
  {C.GREEN}pm open myapp --tool opencode{C.END}

  # 使用 Warp 终端打开项目
  {C.GREEN}pm open myapp --term Warp{C.END}

  # 组合使用：用 Warp + VS Code 打开
  {C.GREEN}pm open myapp --tool opencode --term Warp{C.END}

  # 在当前 tab 直接执行（不新建窗口）
  {C.GREEN}pm open myapp --current{C.END}

  # 当前 tab 执行并启动工具
  {C.GREEN}pm open myapp --current --tool claude{C.END}"""

    # 支持的工具说明
    tools_help = f"""{C.BOLD}{C.BLUE}Supported Tools:{C.END}
  {C.CYAN}gemini{C.END}     Google Gemini CLI
  {C.CYAN}opencode{C.END}   VS Code
  {C.CYAN}codex{C.END}      OpenAI Codex CLI
  {C.CYAN}claude{C.END}     Claude Code
  {C.CYAN}shell{C.END}      仅打开终端"""

    # 支持的终端说明
    terminals_help = f"""{C.BOLD}{C.BLUE}Supported Terminals:{C.END}
  {C.CYAN}Terminal{C.END}   macOS 默认终端 (默认)
  {C.CYAN}Warp{C.END}     Warp 终端"""

    parser = argparse.ArgumentParser(
        prog='pm',
        description=description,
        epilog=f"{examples}\n\n{tools_help}\n\n{terminals_help}\n",
        formatter_class=CustomHelpFormatter,
        add_help=True
    )

    subparsers = parser.add_subparsers(dest="command", title='Commands', metavar='')

    # add 命令
    parser_add = subparsers.add_parser(
        'add',
        help='添加当前目录为项目',
        description='将当前工作目录注册为一个项目，使用指定的别名',
        prog='pm add'
    )
    parser_add.add_argument('name', metavar='<alias>', help='项目别名（用于快速打开）')
    parser_add.add_argument('description', nargs='?', default='', help='项目描述（可选）')

    # list 命令
    subparsers.add_parser(
        'list',
        help='列出所有已注册的项目',
        description='显示所有已注册项目的别名、描述和路径',
        prog='pm list'
    )

    # open 命令
    parser_open = subparsers.add_parser(
        'open',
        help='在新终端中打开项目',
        description='切换到项目目录并在新终端窗口中启动',
        prog='pm open'
    )
    parser_open.add_argument('name', metavar='<alias>', help='项目别名')
    parser_open.add_argument(
        '-t', '--tool',
        choices=['gemini', 'opencode', 'codex', 'claude', 'shell'],
        metavar='<tool>',
        help='直接启动指定工具（不显示菜单）'
    )
    parser_open.add_argument(
        '-T', '--term',
        choices=['Terminal', 'Warp'],
        default='Terminal',
        metavar='<terminal>',
        help='目标终端应用（默认: Terminal）'
    )
    parser_open.add_argument(
        '-c', '--current',
        action='store_true',
        help='在当前 tab 中执行命令（不新建窗口或 tab）'
    )

    # menu 命令（隐藏）
    subparsers.add_parser('menu', help=argparse.SUPPRESS)

    return parser

def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.command == 'add':
        add_project(args.name, args.description)
    elif args.command == 'list':
        list_projects()
    elif args.command == 'open':
        open_project(args.name, args.tool, args.term, args.current)
    elif args.command == 'menu':
        show_menu()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()