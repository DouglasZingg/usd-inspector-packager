from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from usd_tool.core.loader import open_stage
from usd_tool.core.inspector import scan_stage, ValidationResult

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QHeaderView,
    QCheckBox,
    QMessageBox,
)


@dataclass
class ValidationResult:
    level: str
    category: str
    message: str
    prim: str
    path: str


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("USD Inspector & Packager")
        self.resize(1050, 700)

        self._build_ui()
        self._wire_signals()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setSpacing(10)

        # ---------- File pickers ----------
        picker_row = QHBoxLayout()

        self.le_usd_path = QLineEdit()
        self.le_usd_path.setPlaceholderText("Select a .usd/.usda/.usdc/.usdz file...")

        self.btn_browse_usd = QPushButton("Browse USD...")

        self.le_output_dir = QLineEdit()
        self.le_output_dir.setPlaceholderText("Select an output folder...")

        self.btn_browse_out = QPushButton("Browse Output...")

        picker_row.addWidget(QLabel("USD File:"))
        picker_row.addWidget(self.le_usd_path, 3)
        picker_row.addWidget(self.btn_browse_usd)

        picker_row.addSpacing(12)

        picker_row.addWidget(QLabel("Output:"))
        picker_row.addWidget(self.le_output_dir, 3)
        picker_row.addWidget(self.btn_browse_out)

        layout.addLayout(picker_row)

        # ---------- Options row ----------
        options_row = QHBoxLayout()
        self.cb_relative_paths = QCheckBox("Portable mode (rewrite paths to relative)")
        self.cb_hash_files = QCheckBox("Hash files (manifest)")
        options_row.addWidget(self.cb_relative_paths)
        options_row.addWidget(self.cb_hash_files)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        # ---------- Buttons ----------
        btn_row = QHBoxLayout()
        self.btn_scan = QPushButton("Scan")
        self.btn_package = QPushButton("Package")
        self.btn_export = QPushButton("Export Report")
        btn_row.addWidget(self.btn_scan)
        btn_row.addWidget(self.btn_package)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # ---------- Results table ----------
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Level", "Category", "Message", "Prim", "Path"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 4)

        # ---------- Log output ----------
        layout.addWidget(QLabel("Log:"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log, 2)

    def _wire_signals(self):
        self.btn_browse_usd.clicked.connect(self._pick_usd_file)
        self.btn_browse_out.clicked.connect(self._pick_output_folder)

        self.btn_scan.clicked.connect(self._on_scan)
        self.btn_package.clicked.connect(self._on_package)
        self.btn_export.clicked.connect(self._on_export)

    # ---------- UI helpers ----------
    def _pick_usd_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select USD File",
            "",
            "USD Files (*.usd *.usda *.usdc *.usdz);;All Files (*.*)",
        )
        if path:
            self.le_usd_path.setText(path)
            self._log(f"Selected USD: {path}")

    def _pick_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", "")
        if folder:
            self.le_output_dir.setText(folder)
            self._log(f"Selected Output: {folder}")

    def _log(self, msg: str):
        self.log.append(msg)

    def _clear_results(self):
        self.table.setRowCount(0)

    def _add_result_row(self, r: ValidationResult):
        row = self.table.rowCount()
        self.table.insertRow(row)

        items = [
            QTableWidgetItem(r.level),
            QTableWidgetItem(r.category),
            QTableWidgetItem(r.message),
            QTableWidgetItem(r.prim),
            QTableWidgetItem(r.path),
        ]

        # Make them non-editable
        for it in items:
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)

        # Color by severity
        lvl = r.level.upper()
        if lvl == "ERROR":
            items[0].setForeground(Qt.red)
        elif lvl == "WARNING":
            items[0].setForeground(Qt.darkYellow)
        else:
            items[0].setForeground(Qt.darkGreen)

        for col, it in enumerate(items):
            self.table.setItem(row, col, it)

    def _validate_inputs(self) -> tuple[Path | None, Path | None]:
        usd_path = Path(self.le_usd_path.text().strip())
        out_dir = Path(self.le_output_dir.text().strip()) if self.le_output_dir.text().strip() else None

        if not usd_path.exists():
            QMessageBox.warning(self, "Missing USD", "Please select a valid USD file.")
            return None, None

        return usd_path, out_dir

    # ---------- Button actions (placeholders for now) ----------
    def _on_scan(self):
        usd_path, _ = self._validate_inputs()
        if not usd_path:
            return

        self._log("Scan started...")
        self._clear_results()

        try:
            stage = open_stage(str(usd_path))
            results, deps = scan_stage(stage)
        except Exception as e:
            self._add_result_row(
                ValidationResult(
                    level="ERROR",
                    category="Stage",
                    message=f"Failed to open/scan stage: {e}",
                    prim="",
                    path=str(usd_path),
                )
            )
            self._log(f"Scan failed: {e!r}")
            return

        for r in results:
            self._add_result_row(r)

        self._log(f"Scan finished. Dependencies found: {len(deps)}")


    def _on_package(self):
        usd_path, out_dir = self._validate_inputs()
        if not usd_path:
            return
        if not out_dir or not out_dir.exists():
            QMessageBox.warning(self, "Missing Output Folder", "Please select a valid output folder.")
            return

        portable = self.cb_relative_paths.isChecked()
        hashing = self.cb_hash_files.isChecked()

        self._log(f"Package started... portable={portable} hashing={hashing}")
        self._log("Packaging not implemented yet (Day 2 placeholder).")
        self._log("Package finished (placeholder).")

    def _on_export(self):
        usd_path, _ = self._validate_inputs()
        if not usd_path:
            return

        self._log("Export report not implemented yet (Day 2 placeholder).")
