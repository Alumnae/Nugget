from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                               QFileDialog, QInputDialog, QMessageBox, QComboBox, QLineEdit)
from src.tweaks.tim_overlay import OverlayJob, OverlayState, BOARD_CONFIGS, board_config, overlay_target, overlay_board


def show_tim_overlay(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("TIM 22201 — experimental watch SKU")
    layout = QVBoxLayout(dialog)
    text = QLabel("Import an ORIGINAL overlay exported from this iPhone.\n"
                  "Confirm the active line is TIM_Italy.bundle / 22201.\n"
                  "Adds SKU_CU alongside SKU_EU; does not patch CommCenter.\n"
                  "Acceptance and the temporary activation window are unverified.\n"
                  "Import only stages a change. Use Apply after closing this window.")
    layout.addWidget(text)
    layout.addWidget(QLabel("iPhone model / series (user-provided BoardConfig table):"))
    models = QComboBox()
    models.setObjectName("timBoardConfigCombo")
    models.addItem("Select the iPhone series…", None)
    for series, label, filename, identifiers in BOARD_CONFIGS:
        models.addItem(label, series)
    layout.addWidget(models)
    reference = QLabel("Select a series to see the matching bundle override filename.")
    reference.setObjectName("timBoardConfigReference")
    reference.setWordWrap(True)
    reference.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(reference)

    layout.addWidget(QLabel("TIM carrier settings version (Settings > General > About):"))
    carrier_version = QLineEdit()
    carrier_version.setObjectName("timCarrierVersionEdit")
    carrier_version.setPlaceholderText("For example: 66.0")
    layout.addWidget(carrier_version)
    target_path = QLineEdit()
    target_path.setObjectName("timOverlayTargetEdit")
    target_path.setReadOnly(True)
    layout.addWidget(QLabel("Overlay destination:"))
    layout.addWidget(target_path)

    def update_target():
        try:
            target_path.setText(overlay_target(models.currentData(), overlay_board(models.currentData()), carrier_version.text().strip()))
        except ValueError as error:
            target_path.clear()
            target_path.setPlaceholderText(str(error))

    def update_reference():
        series = models.currentData()
        if series is None:
            reference.setText("Select a series to see the matching bundle override filename.")
        else:
            entry = board_config(series)
            reference.setText("TIM_Italy.bundle / " + entry[2] + "\nIPSW identifiers: " + ", ".join(entry[3]))
        update_target()

    models.currentIndexChanged.connect(update_reference)
    carrier_version.textChanged.connect(update_target)
    if OverlayState.job is not None and OverlayState.job.series is not None:
        models.setCurrentIndex(models.findData(OverlayState.job.series))
        if OverlayState.job.board is not None:
            carrier_version.setText(OverlayState.job.carrier_version or "")
    status = QLabel("Staged: " + str(OverlayState.mode or "none"))
    layout.addWidget(status)

    def invalidate_staged_patch():
        if OverlayState.mode == "patch":
            OverlayState.clear()
            status.setText("Selection changed: import the matching original again before Apply.")
    models.currentIndexChanged.connect(invalidate_staged_patch)
    carrier_version.textChanged.connect(invalidate_staged_patch)

    def stage():
        series = models.currentData()
        if series is None:
            QMessageBox.information(dialog, "Select iPhone", "Select an iPhone series before importing the active overlay.")
            return
        try:
            target = overlay_target(series, overlay_board(models.currentData()), carrier_version.text().strip())
        except ValueError as error:
            QMessageBox.information(dialog, "Overlay destination", str(error))
            return
        source, _ = QFileDialog.getOpenFileName(dialog, "Original active TIM overlay: " + Path(target).name, "", "Plist (*.plist)")
        if not source:
            return
        if Path(source).name != Path(target).name:
            QMessageBox.information(dialog, "Overlay filename mismatch", "The imported original must have the destination filename: " + Path(target).name)
            return
        udid, ok = QInputDialog.getText(dialog, "iPhone identity", "UDID of the iPhone that supplied this overlay:")
        if not ok:
            return
        if QMessageBox.question(dialog, "Confirm carrier identity", "Is this the original active overlay for TIM_Italy.bundle / 22201 on that iPhone? This is not automatically verified.") != QMessageBox.Yes:
            return
        try:
            job = OverlayJob.prepare(source, target.strip(), udid.strip(), Path.home() / "Nugget-TIM-backups", series=series, board=overlay_board(models.currentData()), carrier_version=carrier_version.text().strip())
            OverlayState.job, OverlayState.mode = job, "patch"
            status.setText("Staged: add SKU_CU. Backup: " + str(job.backup_dir))
        except Exception as error:
            QMessageBox.critical(dialog, "Cannot stage overlay", str(error))

    def restore():
        source, _ = QFileDialog.getOpenFileName(dialog, "Select saved manifest.json", str(Path.home() / "Nugget-TIM-backups"), "JSON (*.json)")
        if source:
            try:
                job = OverlayJob.load_backup(source)
                OverlayState.job, OverlayState.mode = job, "restore"
                models.setCurrentIndex(models.findData(job.series) if job.series is not None else 0)
                if job.board is not None:
                    carrier_version.setText(job.carrier_version or "")
                target_path.setText(job.target)
                status.setText("Staged: restore original overlay")
            except Exception as error:
                QMessageBox.critical(dialog, "Cannot stage restore", str(error))

    def clear():
        OverlayState.clear()
        status.setText("Staged: none")

    for label, callback in [("Import original and stage SKU_CU", stage),
                             ("Stage original from backup", restore),
                             ("Cancel staged overlay", clear), ("Close", dialog.accept)]:
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)
    dialog.exec()
