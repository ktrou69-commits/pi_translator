import os
import sys
import subprocess
import webbrowser
import platform

class SystemExecutor:
    """
    Executes system-level commands in a cross-platform way.
    Supports macOS, Windows, and Linux.
    """

    @staticmethod
    def open_url(url: str):
        """Opens a URL in the default web browser."""
        try:
            webbrowser.open(url)
            return f"Opened URL: {url}"
        except Exception as e:
            return f"Error opening URL: {e}"

    @staticmethod
    def open_path(path: str):
        """Opens a folder or file in the default OS file manager."""
        # Expand user path (e.g., ~ to /Users/kostya)
        expanded_path = os.path.expanduser(path)
        
        if not os.path.exists(expanded_path):
            return f"Error: Path does not exist: {path}"

        current_os = platform.system()
        try:
            if current_os == "Darwin":  # macOS
                subprocess.run(["open", expanded_path], check=True)
            elif current_os == "Windows":
                os.startfile(expanded_path)
            else:  # Linux
                subprocess.run(["xdg-open", expanded_path], check=True)
            return f"Opened path: {path}"
        except Exception as e:
            return f"Error opening path: {e}"

    @staticmethod
    def run_app(app_name: str):
        """Tries to launch an application by name."""
        current_os = platform.system()
        try:
            if current_os == "Darwin":
                # On macOS we can use 'open -a AppName'
                subprocess.run(["open", "-a", app_name], check=True)
            elif current_os == "Windows":
                # On Windows we can use 'start' or direct execution if in PATH
                subprocess.run(["start", app_name], shell=True, check=True)
            else:
                # On Linux try to run it directly
                subprocess.run([app_name], check=True)
            return f"Launched application: {app_name}"
        except Exception as e:
            return f"Error launching app '{app_name}': {e}"

# Global instance
executor = SystemExecutor()

# Tool definitions for LLMs
TOOL_DEFINITIONS = [
    {
        "name": "open_url",
        "description": "Opens a website or URL in the default browser.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to open (e.g., https://google.com)"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "open_path",
        "description": "Opens a folder or file on the local computer (Downloads, Desktop, etc).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to folder/file. Supports '~' for home directory."}
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_app",
        "description": "Launches an application by its name.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "The name of the application (e.g., 'Telegram', 'Chrome', 'Finder')"}
            },
            "required": ["app_name"]
        }
    }
]
