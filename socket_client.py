"""ChitChat Client

Usage:
    python socket_client.py

When launched, you will be prompted for:
  - Server IP address  (use 127.0.0.1 for localhost)
  - A nickname to display in the chat room

Type a message in the text field at the bottom and press Enter to send.
Close the window to disconnect from the server.
"""
import socket
import threading
import tkinter as tk
from tkinter import simpledialog, scrolledtext


class SocketClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chit Chat")
        self.configure(bg="#330000")
        self.geometry("325x411")
        self.resizable(True, True)

        self.socket = None
        self.reader = None
        self.writer = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.text_area = scrolledtext.ScrolledText(
            self,
            state="disabled",
            bg="#000000",
            fg="#32CD32",
            font=("Monospace", 13, "bold"),
            wrap=tk.WORD,
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)

        self.input_field = tk.Entry(
            self,
            bg="#E6E6FA",
            fg="#000000",
            font=("Tahoma", 11, "bold"),
        )
        self.input_field.insert(0, "Enter your Message:")
        self.input_field.pack(fill=tk.X, side=tk.BOTTOM)
        self.input_field.bind("<Return>", self._send_message)
        self.input_field.focus_set()

    def server_connection(self):
        ip = simpledialog.askstring(
            "Server IP", "Please enter a server IP.", parent=self
        )
        if not ip:
            self.destroy()
            return

        name = simpledialog.askstring(
            "Nickname", "Please enter a nickname.", parent=self
        )
        if not name:
            self.destroy()
            return

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((ip, 1234))
            self.reader = self.socket.makefile(mode="r", buffering=1, encoding="utf-8")
            self.writer = self.socket.makefile(mode="w", buffering=1, encoding="utf-8")
            self.writer.write(name + "\n")
            self.writer.flush()

            threading.Thread(target=self._receive_loop, daemon=True).start()
        except Exception as e:
            print(f"Failed to connect to server at {ip}:1234 - {e}")
            self.destroy()

    def _receive_loop(self):
        try:
            for data in self.reader:
                self._append_text(data.rstrip("\n") + "\n")
        except Exception as e:
            print(f"Error receiving messages from server: {e}")

    def _append_text(self, text):
        self.text_area.configure(state="normal")
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.configure(state="disabled")

    def _send_message(self, event=None):
        data = self.input_field.get()
        self.input_field.delete(0, tk.END)
        if self.writer:
            try:
                self.writer.write(data + "\n")
                self.writer.flush()
            except Exception as e:
                print(f"Failed to send message to server: {e}")

    def _on_close(self):
        if self.socket:
            try:
                self.reader.close()
                self.writer.close()
                self.socket.close()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = SocketClient()
    app.after(100, app.server_connection)
    app.mainloop()
