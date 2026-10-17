from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                               QFileDialog, QInputDialog, QMessageBox)
from src.tweaks.tim_overlay import OverlayJob, OverlayState


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
    status = QLabel("Staged: " + str(OverlayState.mode or "none"))
    layout.addWidget(status)

    def stage():
        source, _ = QFileDialog.getOpenFileName(dialog, "Original active TIM overlay", "", "Plist (*.plist)")
        if not source:
            return
        target, ok = QInputDialog.getText(dialog, "Resolved device path", "Exact original /var/mobile/Library/Carrier Bundles/Overlay/device-*.plist path:")
        if not ok:
            return
        udid, ok = QInputDialog.getText(dialog, "iPhone identity", "UDID of the iPhone that supplied this overlay:")
        if not ok:
            return
        if QMessageBox.question(dialog, "Confirm carrier identity", "Is this the original active overlay for TIM_Italy.bundle / 22201 on that iPhone? This is not automatically verified.") != QMessageBox.Yes:
            return
        try:
            job = OverlayJob.prepare(source, target.strip(), udid.strip(), Path.home() / "Nugget-TIM-backups")
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
