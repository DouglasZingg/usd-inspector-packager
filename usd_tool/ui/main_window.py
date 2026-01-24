from __future__ import annotations

from pathlib import Path

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

from usd_tool.core.loader import open_stage
from usd_tool.core.inspector import scan_stage
from usd_tool.core.reporting import write_report_json
from usd_tool.models import ValidationResult, Level, LEVEL_ORDER
from usd_tool.core.packager import package_usd
from usd_tool.core.batch import batch_scan_full

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("USD Inspector & Packager")
        self.resize(1050, 720)

        self._last_results: list[ValidationResult] = []
        self._last_source_usd: str = ""

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

        self.cb_batch_mode = QCheckBox("Batch mode (USD path is a folder)")
        options_row.addWidget(self.cb_batch_mode)

        # ---------- Severity + view filters ----------
        filters_row = QHBoxLayout()
        self.cb_show_errors = QCheckBox("Errors")
        self.cb_show_warnings = QCheckBox("Warnings")
        self.cb_show_info = QCheckBox("Info")
        self.cb_only_issues = QCheckBox("Only issues (hide INFO)")

        self.cb_show_errors.setChecked(True)
        self.cb_show_warnings.setChecked(True)
        self.cb_show_info.setChecked(True)

        self.lbl_counts = QLabel("Errors: 0 | Warnings: 0 | Info: 0")

        filters_row.addWidget(self.cb_show_errors)
        filters_row.addWidget(self.cb_show_warnings)
        filters_row.addWidget(self.cb_show_info)
        filters_row.addSpacing(12)
        filters_row.addWidget(self.cb_only_issues)
        filters_row.addStretch(1)
        filters_row.addWidget(self.lbl_counts)

        layout.addLayout(filters_row)

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

        self._refresh_table_from_last()

    def _wire_signals(self):
        self.btn_browse_usd.clicked.connect(self._pick_usd_file)
        self.btn_browse_out.clicked.connect(self._pick_output_folder)

        self.btn_scan.clicked.connect(self._on_scan)
        self.btn_package.clicked.connect(self._on_package)
        self.btn_export.clicked.connect(self._on_export)

        self.cb_show_errors.stateChanged.connect(self._refresh_table_from_last)
        self.cb_show_warnings.stateChanged.connect(self._refresh_table_from_last)
        self.cb_show_info.stateChanged.connect(self._refresh_table_from_last)
        self.cb_only_issues.stateChanged.connect(self._refresh_table_from_last)

        self.cb_batch_mode.stateChanged.connect(self._on_batch_mode_changed)


    # ---------- UI helpers ----------
    def _pick_usd_file(self):
        batch_mode = hasattr(self, "cb_batch_mode") and self.cb_batch_mode.isChecked()

        if batch_mode:
            folder = QFileDialog.getExistingDirectory(self, "Select USD Folder", "")
            if folder:
                self.le_usd_path.setText(folder)
                self._log(f"Selected USD folder: {folder}")
            return

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

        for it in items:
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)

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
        usd_text = self.le_usd_path.text().strip()
        out_text = self.le_output_dir.text().strip()

        usd_path = Path(usd_text) if usd_text else Path("")
        out_dir = Path(out_text) if out_text else None

        batch_mode = hasattr(self, "cb_batch_mode") and self.cb_batch_mode.isChecked()

        if not usd_text or not usd_path.exists():
            QMessageBox.warning(self, "Missing Path", "Please select a valid USD file (or folder in Batch mode).")
            return None, None

        if batch_mode:
            if not usd_path.is_dir():
                QMessageBox.warning(self, "Batch Mode", "Batch mode is enabled-please select a folder.")
                return None, None
        else:
            if not usd_path.is_file():
                QMessageBox.warning(self, "Single Mode", "Batch mode is off-please select a USD file.")
                return None, None

        return usd_path, out_dir


    # ---------- Sorting/filtering ----------
    def _sorted_results(self, results: list[ValidationResult]) -> list[ValidationResult]:
        def key(r: ValidationResult):
            lvl = Level(r.level) if r.level in Level._value2member_map_ else Level.INFO
            return (LEVEL_ORDER[lvl], r.category, r.prim, r.path, r.message)

        return sorted(results, key=key)

    def _update_counts_label(self, results: list[ValidationResult]) -> None:
        e = sum(1 for r in results if r.level == "ERROR")
        w = sum(1 for r in results if r.level == "WARNING")
        i = sum(1 for r in results if r.level == "INFO")
        self.lbl_counts.setText(f"Errors: {e} | Warnings: {w} | Info: {i}")

    def _apply_filters(self, results: list[ValidationResult]) -> list[ValidationResult]:
        show_error = self.cb_show_errors.isChecked()
        show_warn = self.cb_show_warnings.isChecked()
        show_info = self.cb_show_info.isChecked()
        only_issues = self.cb_only_issues.isChecked()

        out: list[ValidationResult] = []
        for r in results:
            # Keep batch headers visible even when hiding INFO
            if r.category == "Batch":
                out.append(r)
                continue

            if only_issues and r.level == "INFO":
                continue
            if r.level == "ERROR" and not show_error:
                continue
            if r.level == "WARNING" and not show_warn:
                continue
            if r.level == "INFO" and not show_info:
                continue
            out.append(r)
        return out


    def _refresh_table_from_last(self):
        self._clear_results()
        self._update_counts_label(self._last_results)

        filtered = self._apply_filters(self._last_results)
        filtered = self._sorted_results(filtered)

        for r in filtered:
            self._add_result_row(r)

    # ---------- Button actions ----------
    def _on_scan(self):
        usd_path, _ = self._validate_inputs()
        if not usd_path:
            return

        batch_mode = hasattr(self, "cb_batch_mode") and self.cb_batch_mode.isChecked()

        self._log("Scan started...")
        self._clear_results()

        try:
            if batch_mode:
                self._log(f"Batch scan folder: {usd_path}")
                results = batch_scan_full(str(usd_path))

                self._last_source_usd = str(usd_path)
                self._last_results = results

                self._refresh_table_from_last()
                self._log(f"Batch scan finished. Total rows: {len(results)}")
            else:
                stage = open_stage(str(usd_path))
                results, deps = scan_stage(stage)

                self._last_source_usd = str(usd_path)
                self._last_results = results

                self._refresh_table_from_last()
                self._log(f"Scan finished. Dependencies found: {len(deps)}")

        except Exception as e:
            self._last_source_usd = str(usd_path)
            self._last_results = [
                ValidationResult(
                    level="ERROR",
                    category="Stage" if not batch_mode else "Batch",
                    message=f"Scan failed: {e}",
                    prim="",
                    path=str(usd_path),
                )
            ]
            self._refresh_table_from_last()
            self._log(f"Scan failed: {e!r}")


    def _on_package(self):
        usd_path, out_dir = self._validate_inputs()
        if not usd_path:
            return
        if not out_dir:
            QMessageBox.warning(self, "Missing Output Folder", "Please select an output folder.")
            return

        portable = self.cb_relative_paths.isChecked()
        hashing = self.cb_hash_files.isChecked()
        batch_mode = getattr(self, "cb_batch_mode", None) and self.cb_batch_mode.isChecked()

        self._log("Package started...")
        if batch_mode:
            self._log(f"Batch packaging folder -> {usd_path}")
        else:
            self._log(f"Single packaging USD -> {usd_path}")
        self._log(f"Output folder -> {out_dir}")
        if portable:
            self._log("Portable mode enabled (rewrite paths).")
        if hashing:
            self._log("Hashing enabled (sha256).")

        try:
            if batch_mode:
                # Output root for batch
                batch_out = out_dir / f"{usd_path.stem}_BATCH_PACKAGE"
                batch_out.mkdir(parents=True, exist_ok=True)

                summary = batch_package(
                    folder=str(usd_path),
                    output_root=str(batch_out),
                    compute_hashes=hashing,
                    portable=portable,
                    version="0.1.0",
                )

                summary_path = write_batch_summary(str(batch_out / "batch_summary.json"), summary)

                self._last_results.append(
                    ValidationResult(
                        level="INFO",
                        category="Batch",
                        message=f"Batch packaged {summary['file_count']} files "
                                f"(failed {summary['totals']['files_failed']}). "
                                f"Copied {summary['totals']['copied_total']}, missing {summary['totals']['missing_total']}.",
                        prim="",
                        path=str(batch_out),
                    )
                )
                self._last_results.append(
                    ValidationResult(
                        level="INFO",
                        category="Batch",
                        message="Wrote batch_summary.json",
                        prim="",
                        path=str(summary_path),
                    )
                )
                self._refresh_table_from_last()
                self._log(f"Batch finished. Summary: {summary_path}")

            else:
                # Single package output root
                pkg_root = out_dir / f"{usd_path.stem}_PACKAGE"

                result = package_usd(
                    str(usd_path),
                    str(pkg_root),
                    compute_hashes=hashing,
                    portable=portable,
                    version="0.1.0",
                )

                # Unpack safely
                copied = []
                missing = []
                manifest_path = ""
                rewrite_stats = None

                if isinstance(result, tuple) and len(result) == 5:
                    copied, _mapping, missing, manifest_path, rewrite_stats = result
                elif isinstance(result, tuple) and len(result) == 4:
                    copied, _mapping, missing, manifest_path = result
                else:
                    raise RuntimeError(f"Unexpected package_usd return: {type(result)} {result!r}")

                self._log(f"Package finished. Files copied: {len(copied)} | Missing: {len(missing)}")
                if manifest_path:
                    self._log(f"Manifest: {manifest_path}")
                if rewrite_stats is not None:
                    self._log(f"Portable rewrite: {rewrite_stats}")

                self._last_results.append(
                    ValidationResult(
                        level="INFO",
                        category="Packager",
                        message=f"Packaged {len(copied)} files (missing {len(missing)})",
                        prim="",
                        path=str(pkg_root),
                    )
                )

                for m in missing:
                    cat = getattr(m, "category", "Missing")
                    src = getattr(m, "src", "")
                    self._last_results.append(
                        ValidationResult(
                            level="WARNING",
                            category=cat,
                            message="Missing during packaging (skipped).",
                            prim="",
                            path=str(src),
                        )
                    )

                self._refresh_table_from_last()

        except Exception as e:
            QMessageBox.critical(self, "Package failed", str(e))
            self._log(f"Package failed: {e!r}")
            return


    def _on_export(self):
        if not self._last_results or not self._last_source_usd:
            QMessageBox.information(self, "Nothing to export", "Run Scan first.")
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save report.json",
            "report.json",
            "JSON (*.json);;All Files (*.*)",
        )
        if not out_path:
            return

        try:
            saved = write_report_json(
                out_path=out_path,
                source_usd=self._last_source_usd,
                results=self._last_results,
                version="0.1.0",
            )
            self._log(f"Exported report: {saved}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            self._log(f"Export failed: {e!r}")

    def _on_batch_mode_changed(self):
        p = Path(self.le_usd_path.text().strip()) if self.le_usd_path.text().strip() else None
        if not p:
            return

        if self.cb_batch_mode.isChecked() and p.exists() and p.is_file():
            self.le_usd_path.clear()
            self._log("Batch mode enabled: cleared USD file path (select a folder).")
        elif (not self.cb_batch_mode.isChecked()) and p.exists() and p.is_dir():
            self.le_usd_path.clear()
            self._log("Batch mode disabled: cleared USD folder path (select a file).")
