from __future__ import annotations

import tkinter as tk
from queue import Empty, Queue
from threading import Thread
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .backup import SnapshotError, compare_snapshots, create_snapshot, inspect_snapshot, restore_snapshot
from .storage import app_data_dir, load_profiles, save_profiles


def history_hash_label(digest: str) -> str:
    return digest[:20] + "…" if digest else "Не вычислен"


class SaveHarborApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SaveHarbor — game save backups")
        self.root.geometry("1050x690")
        self.root.minsize(850, 560)
        self.root.configure(bg="#0b1220")
        self.profiles = load_profiles()
        self.snapshots: list[Path] = []
        self._work_queue: Queue[tuple[bool, object, object, object]] = Queue()
        self._action_buttons: list[ttk.Button] = []
        self._style()
        self._build()
        self._refresh_profiles()

    def _style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0b1220")
        style.configure("Panel.TFrame", background="#111b2c")
        style.configure("TLabel", background="#0b1220", foreground="#e5eefc", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#0b1220", foreground="#93a4bd", font=("Segoe UI", 9))
        style.configure("Title.TLabel", background="#0b1220", foreground="#f4f8ff", font=("Segoe UI", 23, "bold"))
        style.configure("PanelTitle.TLabel", background="#111b2c", foreground="#f4f8ff", font=("Segoe UI", 11, "bold"))
        style.configure("TButton", background="#24344e", foreground="#f4f8ff", borderwidth=0, padding=(11, 8), font=("Segoe UI", 9, "bold"))
        style.map("TButton", background=[("active", "#314968"), ("disabled", "#1c293c")])
        style.configure("Accent.TButton", background="#24c6a6", foreground="#05211e")
        style.map("Accent.TButton", background=[("active", "#54dfc2")])
        style.configure("Treeview", background="#111b2c", fieldbackground="#111b2c", foreground="#dce8fa", rowheight=29, borderwidth=0)
        style.configure("Treeview.Heading", background="#1b2a41", foreground="#bfcee3", font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("Treeview", background=[("selected", "#214c60")])
        style.configure("TCombobox", fieldbackground="#111b2c", background="#24344e", foreground="#e5eefc")

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 17))
        ttk.Label(header, text="SaveHarbor", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Резервные копии игровых сохранений — локально, с проверкой SHA-256", style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

        profile_bar = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        profile_bar.pack(fill="x", pady=(0, 15))
        ttk.Label(profile_bar, text="Профиль игры", style="PanelTitle.TLabel").pack(side="left", padx=(2, 10))
        self.profile_var = tk.StringVar()
        self.profile_box = ttk.Combobox(profile_bar, textvariable=self.profile_var, state="readonly", width=30)
        self.profile_box.pack(side="left", padx=4)
        self.profile_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_history())
        ttk.Button(profile_bar, text="＋ Добавить папку сохранений", command=self._add_profile).pack(side="left", padx=8)
        ttk.Button(profile_bar, text="Удалить профиль", command=self._remove_profile).pack(side="left", padx=2)
        ttk.Button(profile_bar, text="Папка архивов", command=self._open_backup_dir).pack(side="right", padx=4)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 14))
        self.backup_button = ttk.Button(actions, text="Создать снимок", style="Accent.TButton", command=self._create_backup)
        self.backup_button.pack(side="left")
        self.compare_button = ttk.Button(actions, text="Сравнить два снимка", command=self._compare)
        self.compare_button.pack(side="left", padx=8)
        self.restore_button = ttk.Button(actions, text="Восстановить выбранный", command=self._restore)
        self.restore_button.pack(side="left")
        self.verify_button = ttk.Button(actions, text="Проверить SHA-256", command=self._verify)
        self.verify_button.pack(side="left", padx=8)
        self._action_buttons = [self.backup_button, self.compare_button, self.restore_button, self.verify_button]

        card = ttk.Frame(outer, style="Panel.TFrame", padding=13)
        card.pack(fill="both", expand=True)
        ttk.Label(card, text="История резервных копий", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 9))
        columns = ("created", "count", "size", "hash")
        self.history = ttk.Treeview(card, columns=columns, show="headings", selectmode="extended")
        for col, title, width in (("created", "Создано (UTC)", 220), ("count", "Файлов", 90), ("size", "Размер", 140), ("hash", "SHA-256 архива", 390)):
            self.history.heading(col, text=title)
            self.history.column(col, width=width, anchor="w" if col in ("created", "hash") else "center")
        self.history.pack(fill="both", expand=True)
        self.history.bind("<Double-1>", lambda _event: self._verify())
        self.status = tk.StringVar(value="Создайте профиль, выбрав папку сохранений игры.")
        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel", wraplength=950).pack(fill="x", pady=(11, 0))
        ttk.Label(outer, text="Восстановление накладывает файлы снимка и перезаписывает совпадающие пути; лишние файлы в папке сохраняются.", style="Muted.TLabel", wraplength=950).pack(fill="x", pady=(4, 0))
        self.root.after(100, self._poll_work_queue)

    def _run_background(self, label: str, operation, success, failure) -> None:
        for button in self._action_buttons:
            button.state(["disabled"])
        self.status.set(label)

        def run() -> None:
            try:
                self._work_queue.put((True, operation(), success, failure))
            except Exception as exc:
                self._work_queue.put((False, exc, success, failure))

        Thread(target=run, name="SaveHarbor-operation", daemon=True).start()

    def _poll_work_queue(self) -> None:
        try:
            succeeded, result, on_success, on_failure = self._work_queue.get_nowait()
        except Empty:
            self.root.after(100, self._poll_work_queue)
            return
        for button in self._action_buttons:
            button.state(["!disabled"])
        if succeeded:
            on_success(result)
        else:
            on_failure(result)
        self.root.after(100, self._poll_work_queue)

    def _selected_profile(self) -> dict[str, str] | None:
        name = self.profile_var.get()
        return next((p for p in self.profiles if p["name"] == name), None)

    def _refresh_profiles(self) -> None:
        names = [p["name"] for p in self.profiles]
        self.profile_box["values"] = names
        if names and self.profile_var.get() not in names:
            self.profile_var.set(names[0])
        self._refresh_history()

    def _refresh_history(self) -> None:
        for item in self.history.get_children():
            self.history.delete(item)
        profile = self._selected_profile()
        self.snapshots = []
        if not profile:
            return
        backup_dir = app_data_dir() / "backups" / self._slug(profile["name"])
        if not backup_dir.exists():
            return
        for archive in sorted(backup_dir.glob("*.saveharbor.zip"), reverse=True):
            try:
                snapshot = inspect_snapshot(archive, calculate_archive_hash=False)
                self.snapshots.append(archive)
                self.history.insert("", "end", iid=str(len(self.snapshots) - 1), values=(snapshot.created_at.replace("T", " "), len(snapshot.files), self._size(snapshot.total_bytes), history_hash_label(snapshot.archive_sha256)))
            except SnapshotError:
                self.history.insert("", "end", values=(archive.name, "не проверен", "—", "архив повреждён или неподдерживаемый"))

    @staticmethod
    def _slug(name: str) -> str:
        import re
        return re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip(".-_")[:80]

    @staticmethod
    def _size(value: int) -> str:
        amount = float(value)
        unit = "B"
        for next_unit in ("KB", "MB", "GB", "TB"):
            if amount < 1024:
                break
            amount /= 1024
            unit = next_unit
        return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"

    def _add_profile(self) -> None:
        folder = filedialog.askdirectory(title="Выберите папку с файлами сохранений игры", mustexist=True)
        if not folder:
            return
        name = self._ask_name(Path(folder).name)
        if not name:
            return
        if any(p["name"].casefold() == name.casefold() for p in self.profiles):
            messagebox.showerror("Профиль уже существует", "Укажите другое название профиля.")
            return
        self.profiles.append({"name": name, "folder": str(Path(folder).resolve())})
        save_profiles(self.profiles)
        self.profile_var.set(name)
        self._refresh_profiles()
        self.status.set(f"Добавлена папка: {folder}")

    def _remove_profile(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return
        if not messagebox.askyesno("Удалить профиль?", f"Профиль «{profile['name']}» будет удалён из списка.\n\nАрхивы резервных копий останутся в папке SaveHarbor."):
            return
        self.profiles = [item for item in self.profiles if item is not profile]
        save_profiles(self.profiles)
        self.profile_var.set("")
        self._refresh_profiles()
        self.status.set("Профиль удалён; его архивы сохранены.")

    def _ask_name(self, initial: str) -> str | None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Название профиля")
        dialog.configure(bg="#0b1220")
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text="Название игры или профиля").pack(padx=18, pady=(18, 4), anchor="w")
        value = tk.StringVar(value=initial)
        entry = ttk.Entry(dialog, textvariable=value, width=38)
        entry.pack(padx=18, pady=6)
        result: list[str | None] = [None]
        def accept() -> None:
            result[0] = value.get().strip() or None
            dialog.destroy()
        ttk.Button(dialog, text="Сохранить", command=accept).pack(padx=18, pady=(6, 16), anchor="e")
        entry.bind("<Return>", lambda _event: accept())
        self.root.wait_window(dialog)
        return result[0]

    def _create_backup(self) -> None:
        profile = self._selected_profile()
        if not profile:
            messagebox.showinfo("Нужен профиль", "Сначала добавьте папку сохранений игры.")
            return
        def completed(result) -> None:
            self._refresh_history()
            self.status.set(f"Снимок создан: {result.file_count} файлов, {self._size(result.total_bytes)}. SHA-256: {result.archive_sha256}")
            messagebox.showinfo("Резервная копия готова", f"Создан архив:\n{result.archive}\n\nФайлов: {result.file_count}\nДанные: {self._size(result.total_bytes)}\nSHA-256: {result.archive_sha256}")
        def failed(exc) -> None:
            messagebox.showerror("Не удалось создать снимок", str(exc))
            self.status.set(str(exc))
        self._run_background("Создаю снимок… Это может занять время для больших папок.", lambda: create_snapshot(Path(profile["folder"]), profile["name"], app_data_dir() / "backups"), completed, failed)

    def _selected_archives(self, count: int) -> list[Path] | None:
        selected = self.history.selection()
        if len(selected) != count:
            messagebox.showinfo("Выбор снимков", f"Выберите ровно {count} снимка в списке.")
            return None
        try:
            return [self.snapshots[int(item)] for item in selected]
        except (ValueError, IndexError):
            messagebox.showerror("Снимок недоступен", "Обновите список и выберите снимок повторно.")
            return None

    def _compare(self) -> None:
        paths = self._selected_archives(2)
        if not paths:
            return
        try:
            left, right = (inspect_snapshot(path, calculate_archive_hash=False) for path in reversed(paths))
            changes = compare_snapshots(left, right)
        except SnapshotError as exc:
            messagebox.showerror("Ошибка сравнения", str(exc))
            return
        lines = [f"Сравнение: {left.created_at} → {right.created_at}", ""]
        for kind, title in (("added", "Добавлено"), ("removed", "Удалено"), ("changed", "Изменено")):
            entries = changes[kind]
            lines.append(f"{title}: {len(entries)}")
            lines.extend(f"  • {name}" for name in entries[:30])
            if len(entries) > 30:
                lines.append(f"  … и ещё {len(entries) - 30}")
        messagebox.showinfo("Разница снимков", "\n".join(lines))

    def _restore(self) -> None:
        paths = self._selected_archives(1)
        profile = self._selected_profile()
        if not paths or not profile:
            return
        try:
            snapshot = inspect_snapshot(paths[0], calculate_archive_hash=False)
        except SnapshotError as exc:
            messagebox.showerror("Снимок не прошёл проверку", str(exc))
            return
        confirmation = messagebox.askyesno("Подтвердите восстановление", f"Снимок проверен. Файлов для восстановления: {len(snapshot.files)}.\n\nСовпадающие пути будут перезаписаны. Другие файлы останутся.\n\nПеред продолжением создайте свежую резервную копию текущего состояния?", icon="warning")
        if not confirmation:
            return
        def restore() -> tuple[object, object]:
            safety = create_snapshot(Path(profile["folder"]), profile["name"] + " safety", app_data_dir() / "backups")
            restored = restore_snapshot(paths[0], Path(profile["folder"]))
            return restored, safety
        def completed(result) -> None:
            restored, safety = result
            self._refresh_history()
            self.status.set(f"Восстановлено {len(restored.files)} файлов. Текущее состояние сохранено: {safety.archive.name}")
            messagebox.showinfo("Восстановление завершено", f"Файлы из снимка восстановлены.\nСтраховочная копия создана: {safety.archive}")
        def failed(exc) -> None:
            messagebox.showerror("Восстановление остановлено", str(exc))
        self._run_background("Проверяю снимок, сохраняю текущее состояние и восстанавливаю файлы…", restore, completed, failed)

    def _verify(self) -> None:
        selected = self.history.selection()
        paths = self._selected_archives(1)
        if not paths:
            return
        selected_item = selected[0]
        def completed(snapshot) -> None:
            if selected_item in self.history.get_children():
                try:
                    index = int(selected_item)
                    if self.snapshots[index] == paths[0]:
                        values = list(self.history.item(selected_item, "values"))
                        values[3] = history_hash_label(snapshot.archive_sha256)
                        self.history.item(selected_item, values=values)
                except (ValueError, IndexError):
                    pass
            self.status.set(f"Проверка пройдена: {len(snapshot.files)} файлов совпадают с манифестом. SHA-256 архива: {snapshot.archive_sha256}")
            messagebox.showinfo("Проверка завершена", f"Все {len(snapshot.files)} файлов прошли SHA-256 проверку.\n\nSHA-256 архива:\n{snapshot.archive_sha256}")
        def failed(exc) -> None:
            messagebox.showerror("Проверка не пройдена", str(exc))
            self.status.set(str(exc))
        self._run_background("Проверяю содержимое архива и SHA-256 файлов…", lambda: inspect_snapshot(paths[0], verify_files=True), completed, failed)

    def _open_backup_dir(self) -> None:
        import os
        import subprocess
        path = app_data_dir() / "backups"
        path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif os.name == "posix":
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror("Не удалось открыть папку", str(exc))
