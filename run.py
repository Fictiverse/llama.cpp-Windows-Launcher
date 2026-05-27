import sys
import os
import json
import subprocess
import webbrowser
import re
import shutil
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFileDialog, QComboBox, QStackedWidget,
    QCheckBox, QSpinBox, QDoubleSpinBox, QGridLayout, QGroupBox, QScrollArea,
    QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QFont


# --- CUSTOM RETRO WIDGETS ---
class NoWheelComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(40)

    def wheelEvent(self, event):
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(35)

    def wheelEvent(self, event):
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(35)

    def wheelEvent(self, event):
        event.ignore()


# Fallback dictionary to protect against old/incomplete JSON preset configurations
DEFAULT_PRESET_VALUES = {
    "model": "",
    "threads": 4,
    "gpu_layers": 99,
    "ctx_size": 16384,
    "batch_size": 1024,
    "jinja": True,
    "chat_template": "",
    "chat_template_file": "",
    "host": "127.0.0.1",
    "port": 8033,
    "cache_type_k": "q8_0",
    "cache_type_v": "q8_0",
    "flash_attn": True,
    "spec_type": "draft-mtp",
    "spec_draft_n_max": 2,
    "split_mode": "row",
    "temp": 0.8,
    "top_k": 40,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
    "interactive": False,
    "color": False,
    "custom_args": "",
    # Advanced: CPU & Scheduler
    "threads_batch": -1,
    "cpu_mask": "",
    "cpu_range": "",
    "cpu_strict": "0",
    "prio": "0",
    "poll": 50,
    # Advanced: Batching
    "ubatch_size": 512,
    "keep": 0,
    "swa_full": False,
    "parallel": 1,
    # Advanced: RoPE
    "rope_scaling": "none",
    "rope_scale": 1.0,
    "rope_freq_base": 0.0,
    "rope_freq_scale": 0.0,
    # Advanced: Memory & HW
    "numa": "none",
    "mlock": False,
    "mmap": True,
    "device": "",
    "lora": "",
    "lora_scaled": "",
    # Advanced: Sampling
    "min_p": 0.05,
    "xtc_prob": 0.0,
    "xtc_thold": 0.1,
    "mirostat": "0",
    "mirostat_lr": 0.1,
    "mirostat_ent": 5.0,
    "dry_mult": 0.0,
    # Advanced: Speculative
    "spec_draft_model": "",
    "spec_draft_ngl": 0,
    "spec_draft_n_min": 0
}

# Wizard Helper Constants
ARCH_TAGS = ["gemma", "mistral", "phi", "qwen35", "qwen", "llama", "falcon", "mpt"]
_QUANT_RE = re.compile(r'[_\-.](?P<q>iq[2-4]|q[2-8])(?:_k(?:_[smlx]+)?|_[0-9]+)?(?:[_.\-]|$)', re.IGNORECASE)
QUANT_VRAM_RATIO = {"iq2": 0.35, "iq3": 0.44, "iq4": 0.55, "q2": 0.35, "q3": 0.44, "q4": 0.55, "q5": 0.67, "q6": 0.75, "q8": 1.00}
_THINK_MODEL_PATTERNS = re.compile(r'\bdeepseek.?r\d\b|\bqwq\b|\bqwen\d[^/\\\\]*think|\br1\b', re.IGNORECASE)


class LlamaLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.config_file = "config.json"
        self.presets_dir = "presets"
        
        self.config = {
            "llama_folder": "",
            "models_path": "",
            "selected_preset": "RTX 3090",
            "autolaunch": False
        }
        self.presets = {}
        
        os.makedirs(self.presets_dir, exist_ok=True)
        self.ensure_default_preset()
        self.load_global_config()
        self.load_all_presets()
        self.init_ui()
        
        # Autolaunch trigger
        if self.config.get("autolaunch", False):
            self.launch_llama()

    def ensure_default_preset(self):
        default_file = os.path.join(self.presets_dir, "RTX 3090.json")
        if not os.path.exists(default_file):
            try:
                with open(default_file, 'w', encoding='utf-8') as f:
                    json.dump(DEFAULT_PRESET_VALUES, f, indent=4)
            except Exception as e:
                print(f"Error creating default preset file: {e}")

    def load_global_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.config["llama_folder"] = loaded.get("llama_folder", self.config["llama_folder"])
                    self.config["models_path"] = loaded.get("models_path", self.config["models_path"])
                    self.config["selected_preset"] = loaded.get("selected_preset", self.config["selected_preset"])
                    self.config["autolaunch"] = loaded.get("autolaunch", self.config["autolaunch"])
            except Exception as e:
                print(f"Error loading global config: {e}")

    def save_global_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving global config: {e}")

    def load_all_presets(self):
        self.presets.clear()
        for file_name in os.listdir(self.presets_dir):
            if file_name.lower().endswith(".json"):
                preset_name = os.path.splitext(file_name)[0]
                file_path = os.path.join(self.presets_dir, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        preset_data = DEFAULT_PRESET_VALUES.copy()
                        preset_data.update(json.load(f))
                        self.presets[preset_name] = preset_data
                except Exception as e:
                    print(f"Error loading preset file {file_name}: {e}")
        if not self.presets:
            self.ensure_default_preset()
            self.load_all_presets()

    def save_preset_file(self, preset_name, data):
        file_path = os.path.join(self.presets_dir, f"{preset_name}.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.presets[preset_name] = data
        except Exception as e:
            print(f"Error writing preset file for {preset_name}: {e}")

    def init_ui(self):
        self.setWindowTitle("Llama.cpp Launcher")
        self.resize(380, 310)  # Compact default height
        
        icon_path = "logo.svg"
        if not os.path.exists(icon_path):
            icon_path = "logo.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setStyleSheet("""
            QWidget {
                background-color: #c0c0c0;
                color: #000000;
            }
            QLabel {
                color: #000000;
            }
            QLineEdit, QComboBox {
                background-color: #ffffff;
                color: #000000;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
                padding: 1px;
                selection-background-color: #000080;
                selection-color: #ffffff;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                color: #000000;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
                padding-right: 14px; 
                min-width: 35px;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 14px;
                height: 10px;
                border-left: 1px solid #808080;
                border-bottom: 1px solid #808080;
                background-color: #c0c0c0;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 14px;
                height: 10px;
                border-left: 1px solid #808080;
                background-color: #c0c0c0;
            }
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                image: url(non_existent_file);
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                width: 3px;
                height: 3px;
            }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                image: url(non_existent_file);
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                width: 3px;
                height: 3px;
            }
            QPushButton {
                background-color: #c0c0c0;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                padding: 3px 8px;
            }
            QPushButton:pressed {
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
                padding-top: 4px;
                padding-left: 9px;
            }
            QGroupBox {
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 6px;
                padding: 0 2px;
            }
            QScrollBar:vertical {
                border: 1px solid #808080;
                background: #d4d0c8;
                width: 14px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-top: 1px solid #ffffff;
                border-left: 1px solid #ffffff;
                border-right: 1px solid #808080;
                border-bottom: 1px solid #808080;
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)
        self.setLayout(main_layout)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.currentChanged.connect(self.on_page_changed) # Bind resizing events
        main_layout.addWidget(self.stacked_widget)

        self.setup_home_view()
        self.setup_app_options_view()
        self.setup_preset_edit_view()
        self.setup_wizard_view()
        self.stacked_widget.setCurrentIndex(0)

    # --- HOME VIEW ---
    def setup_home_view(self):
        home_widget = QWidget()
        layout = QVBoxLayout(home_widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        # Unified layout selectors (Grid) with Preset tall button next to it
        top_hbox = QHBoxLayout()
        top_hbox.setContentsMargins(0, 0, 0, 0)
        top_hbox.setSpacing(4)

        sel_grid = QGridLayout()
        sel_grid.setContentsMargins(0, 0, 0, 0)
        sel_grid.setSpacing(4)

        lbl_preset = QLabel("Preset:")
        lbl_preset.setMinimumWidth(42)
        self.combo_presets = NoWheelComboBox()
        self.update_preset_combo()
        self.combo_presets.currentTextChanged.connect(self.on_preset_changed)
        sel_grid.addWidget(lbl_preset, 0, 0)
        sel_grid.addWidget(self.combo_presets, 0, 1)

        lbl_model = QLabel("Model:")
        lbl_model.setMinimumWidth(42)
        self.combo_models = NoWheelComboBox()
        self.update_model_combo()
        self.combo_models.currentTextChanged.connect(self.on_model_changed) # Auto-save event
        sel_grid.addWidget(lbl_model, 1, 0)
        sel_grid.addWidget(self.combo_models, 1, 1)
        top_hbox.addLayout(sel_grid, stretch=4)

        # Tall button spanning across rows
        btn_manage_preset = QPushButton("Edit\nPreset")
        btn_manage_preset.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        btn_manage_preset.setMinimumWidth(55)
        btn_manage_preset.setMaximumHeight(38)
        btn_manage_preset.clicked.connect(self.go_to_preset_edit)
        top_hbox.addWidget(btn_manage_preset, stretch=1)

        layout.addLayout(top_hbox)

        # Logo display (Compact stacking)
        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        logo_img_path = "logo_full.png"
        if os.path.exists(logo_img_path):
            pixmap = QPixmap(logo_img_path)
            scaled_pixmap = pixmap.scaledToWidth(360, Qt.TransformationMode.SmoothTransformation)
            self.lbl_logo.setPixmap(scaled_pixmap)
        else:
            self.lbl_logo.setText("[logo_full.png not found]")
            self.lbl_logo.setStyleSheet("color: #808080; border: 1px dashed #808080; padding: 10px;")
            
        layout.addWidget(self.lbl_logo)

        # Removed vertical spacer stretch to prevent dead vertical spaces below the logo

        btn_launch = QPushButton("Launch Server")
        btn_launch.setStyleSheet("font-weight: bold;")
        btn_launch.setMinimumHeight(30)
        btn_launch.clicked.connect(self.launch_llama)
        layout.addWidget(btn_launch)

        btn_bench = QPushButton("Run Bench")
        btn_bench.setMinimumHeight(26)
        btn_bench.clicked.connect(self.launch_bench)
        layout.addWidget(btn_bench)

        btn_web_ui = QPushButton("Open Web UI")
        btn_web_ui.setMinimumHeight(26)
        btn_web_ui.clicked.connect(self.open_web_ui)
        layout.addWidget(btn_web_ui)

        btn_options = QPushButton("Options...")
        btn_options.setMinimumHeight(26)
        btn_options.clicked.connect(self.go_to_app_options)
        layout.addWidget(btn_options)

        self.stacked_widget.addWidget(home_widget)

    # --- APP OPTIONS VIEW (Page 1) ---
    def setup_app_options_view(self):
        options_widget = QWidget()
        layout = QVBoxLayout(options_widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        group_paths = QGroupBox("Application Settings")
        paths_grid = QGridLayout(group_paths)
        paths_grid.setContentsMargins(6, 6, 6, 6)
        paths_grid.setSpacing(4)
        
        self.input_llama_folder = QLineEdit(self.config["llama_folder"])
        btn_browse_folder = QPushButton("...")
        btn_browse_folder.clicked.connect(self.browse_llama_folder)
        paths_grid.addWidget(QLabel("Llama.cpp:"), 0, 0)
        paths_grid.addWidget(self.input_llama_folder, 0, 1)
        paths_grid.addWidget(btn_browse_folder, 0, 2)

        self.input_models_path = QLineEdit(self.config["models_path"])
        btn_browse_models = QPushButton("...")
        btn_browse_models.clicked.connect(self.browse_models_path)
        paths_grid.addWidget(QLabel("Models:"), 1, 0)
        paths_grid.addWidget(self.input_models_path, 1, 1)
        paths_grid.addWidget(btn_browse_models, 1, 2)

        self.check_autolaunch = QCheckBox("Autolaunch last preset on startup")
        self.check_autolaunch.setChecked(self.config.get("autolaunch", False))
        paths_grid.addWidget(self.check_autolaunch, 2, 0, 1, 3)
        
        layout.addWidget(group_paths)
        layout.addStretch()

        # Save & Cancel Buttons for app settings
        nav_buttons = QHBoxLayout()
        nav_buttons.setSpacing(4)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("font-weight: bold;")
        btn_save.clicked.connect(self.save_app_options)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.discard_changes_and_exit)
        nav_buttons.addWidget(btn_save)
        nav_buttons.addWidget(btn_cancel)
        layout.addLayout(nav_buttons)

        self.stacked_widget.addWidget(options_widget)

    # --- PRESET EDIT VIEW (Page 2) ---
    def setup_preset_edit_view(self):
        preset_widget = QWidget()
        layout = QVBoxLayout(preset_widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # Preset name editor at the top
        name_group = QGroupBox("Target Profile Name")
        name_layout = QHBoxLayout(name_group)
        name_layout.setContentsMargins(6, 6, 6, 6)
        name_layout.addWidget(QLabel("Preset Name:"))
        self.input_preset_name = QLineEdit()
        name_layout.addWidget(self.input_preset_name)
        layout.addWidget(name_group)

        # Integrated Wizard button directly under Profile Name
        btn_wizard = QPushButton("Wizard (Autodetect Profile Settings)")
        btn_wizard.setMinimumHeight(24)
        btn_wizard.setStyleSheet("font-weight: bold; color: #000080;")
        btn_wizard.clicked.connect(self.go_to_wizard)
        layout.addWidget(btn_wizard)

        # Advanced Mode Selector
        self.check_advanced_mode = QCheckBox("Advanced Mode")
        self.check_advanced_mode.stateChanged.connect(self.toggle_advanced_visibility)
        layout.addWidget(self.check_advanced_mode)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 4, 0)
        self.scroll_layout.setSpacing(4)

        # --- PERFORMANCE (Standard) ---
        group_perf = QGroupBox("Performance")
        perf_grid = QGridLayout(group_perf)
        perf_grid.setContentsMargins(6, 6, 6, 6)
        perf_grid.setSpacing(4)

        self.spin_threads = NoWheelSpinBox()
        self.spin_threads.setRange(1, 256)
        perf_grid.addWidget(QLabel("Threads:"), 0, 0)
        perf_grid.addWidget(self.spin_threads, 0, 1)

        self.spin_gpu = NoWheelSpinBox()
        self.spin_gpu.setRange(0, 999)
        perf_grid.addWidget(QLabel("GPU layers:"), 0, 2)
        perf_grid.addWidget(self.spin_gpu, 0, 3)

        self.spin_ctx = NoWheelSpinBox()
        self.spin_ctx.setRange(0, 512000)
        self.spin_ctx.setSingleStep(1024)
        perf_grid.addWidget(QLabel("Context:"), 1, 0)
        perf_grid.addWidget(self.spin_ctx, 1, 1)

        self.spin_batch = NoWheelSpinBox()
        self.spin_batch.setRange(8, 8192)
        self.spin_batch.setSingleStep(128)
        perf_grid.addWidget(QLabel("Batch:"), 1, 2)
        perf_grid.addWidget(self.spin_batch, 1, 3)

        self.check_flash_attn = QCheckBox("Flash Attention")
        perf_grid.addWidget(self.check_flash_attn, 2, 0, 1, 2)

        self.combo_split_mode = NoWheelComboBox()
        self.combo_split_mode.addItems(["none", "row", "cl", "layer"])
        perf_grid.addWidget(QLabel("Split mode:"), 2, 2)
        perf_grid.addWidget(self.combo_split_mode, 2, 3)

        self.scroll_layout.addWidget(group_perf)

        # --- PERFORMANCE (Advanced) ---
        self.group_adv_perf = QGroupBox("Performance (Advanced)")
        adv_perf_grid = QGridLayout(self.group_adv_perf)
        adv_perf_grid.setContentsMargins(6, 6, 6, 6)
        adv_perf_grid.setSpacing(4)

        self.spin_threads_batch = NoWheelSpinBox()
        self.spin_threads_batch.setRange(-1, 256)
        adv_perf_grid.addWidget(QLabel("Threads batch:"), 0, 0)
        adv_perf_grid.addWidget(self.spin_threads_batch, 0, 1)

        self.spin_parallel = NoWheelSpinBox()
        self.spin_parallel.setRange(1, 64)
        adv_perf_grid.addWidget(QLabel("Parallel seq:"), 0, 2)
        adv_perf_grid.addWidget(self.spin_parallel, 0, 3)

        self.spin_keep = NoWheelSpinBox()
        self.spin_keep.setRange(-1, 8192)
        adv_perf_grid.addWidget(QLabel("Keep tokens:"), 1, 0)
        adv_perf_grid.addWidget(self.spin_keep, 1, 1)

        self.combo_cpu_strict = NoWheelComboBox()
        self.combo_cpu_strict.addItems(["0", "1"])
        adv_perf_grid.addWidget(QLabel("CPU strict:"), 1, 2)
        adv_perf_grid.addWidget(self.combo_cpu_strict, 1, 3)

        self.combo_prio = NoWheelComboBox()
        self.combo_prio.addItems(["-1", "0", "1", "2", "3"])
        adv_perf_grid.addWidget(QLabel("Priority:"), 2, 0)
        adv_perf_grid.addWidget(self.combo_prio, 2, 1)

        self.spin_poll = NoWheelSpinBox()
        self.spin_poll.setRange(0, 100)
        adv_perf_grid.addWidget(QLabel("Polling wait:"), 2, 2)
        adv_perf_grid.addWidget(self.spin_poll, 2, 3)

        self.input_cpu_mask = QLineEdit()
        adv_perf_grid.addWidget(QLabel("CPU Mask:"), 3, 0)
        adv_perf_grid.addWidget(self.input_cpu_mask, 3, 1)

        self.input_cpu_range = QLineEdit()
        adv_perf_grid.addWidget(QLabel("CPU Range:"), 3, 2)
        adv_perf_grid.addWidget(self.input_cpu_range, 3, 3)

        self.spin_ubatch = NoWheelSpinBox()
        self.spin_ubatch.setRange(1, 8192)
        self.spin_ubatch.setSingleStep(128)
        adv_perf_grid.addWidget(QLabel("Phys batch:"), 4, 0)
        adv_perf_grid.addWidget(self.spin_ubatch, 4, 1)

        self.check_swa_full = QCheckBox("Full-size SWA")
        adv_perf_grid.addWidget(self.check_swa_full, 4, 2, 1, 2)

        self.scroll_layout.addWidget(self.group_adv_perf)

        # --- RoPE SCALING (Advanced) ---
        self.group_rope = QGroupBox("RoPE Context Scaling")
        rope_grid = QGridLayout(self.group_rope)
        rope_grid.setContentsMargins(6, 6, 6, 6)
        rope_grid.setSpacing(4)

        self.combo_rope_scaling = NoWheelComboBox()
        self.combo_rope_scaling.addItems(["none", "linear", "yarn"])
        rope_grid.addWidget(QLabel("Scaling:"), 0, 0)
        rope_grid.addWidget(self.combo_rope_scaling, 0, 1)

        self.double_rope_scale = NoWheelDoubleSpinBox()
        self.double_rope_scale.setRange(0.0, 100.0)
        rope_grid.addWidget(QLabel("Factor:"), 0, 2)
        rope_grid.addWidget(self.double_rope_scale, 0, 3)

        self.double_rope_freq_base = NoWheelDoubleSpinBox()
        self.double_rope_freq_base.setRange(0.0, 1000000.0)
        rope_grid.addWidget(QLabel("Base:"), 1, 0)
        rope_grid.addWidget(self.double_rope_freq_base, 1, 1)

        self.double_rope_freq_scale = NoWheelDoubleSpinBox()
        self.double_rope_freq_scale.setRange(0.0, 100.0)
        rope_grid.addWidget(QLabel("Scale freq:"), 1, 2)
        rope_grid.addWidget(self.double_rope_freq_scale, 1, 3)

        self.scroll_layout.addWidget(self.group_rope)

        # --- HARDWARE & MEMORY (Advanced) ---
        self.group_hw_mem = QGroupBox("Memory & Co-Processors")
        hw_mem_grid = QGridLayout(self.group_hw_mem)
        hw_mem_grid.setContentsMargins(6, 6, 6, 6)
        hw_mem_grid.setSpacing(4)

        self.combo_numa = NoWheelComboBox()
        self.combo_numa.addItems(["none", "distribute", "isolate", "numactl"])
        hw_mem_grid.addWidget(QLabel("NUMA strategy:"), 0, 0)
        hw_mem_grid.addWidget(self.combo_numa, 0, 1)

        self.check_mlock = QCheckBox("mlock")
        hw_mem_grid.addWidget(self.check_mlock, 0, 2)

        self.check_mmap = QCheckBox("mmap")
        hw_mem_grid.addWidget(self.check_mmap, 0, 3)

        self.input_device = QLineEdit()
        hw_mem_grid.addWidget(QLabel("Devices list:"), 1, 0)
        hw_mem_grid.addWidget(self.input_device, 1, 1, 1, 3)

        self.input_lora = QLineEdit()
        hw_mem_grid.addWidget(QLabel("LoRA adapter:"), 2, 0)
        hw_mem_grid.addWidget(self.input_lora, 2, 1, 1, 3)

        self.input_lora_scaled = QLineEdit()
        hw_mem_grid.addWidget(QLabel("LoRA scaled:"), 3, 0)
        hw_mem_grid.addWidget(self.input_lora_scaled, 3, 1, 1, 3)

        self.scroll_layout.addWidget(self.group_hw_mem)

        # --- KV CACHE (Standard) ---
        group_cache = QGroupBox("KV Cache Type")
        cache_grid = QGridLayout(group_cache)
        cache_grid.setContentsMargins(6, 6, 6, 6)
        cache_grid.setSpacing(4)

        self.combo_ctk = NoWheelComboBox()
        self.combo_ctk.addItems(["f16", "q8_0", "q4_0", "f32", "bf16", "q4_1", "iq4_nl", "q5_0", "q5_1"])
        cache_grid.addWidget(QLabel("Cache K:"), 0, 0)
        cache_grid.addWidget(self.combo_ctk, 0, 1)

        self.combo_ctv = NoWheelComboBox()
        self.combo_ctv.addItems(["f16", "q8_0", "q4_0", "f32", "bf16", "q4_1", "iq4_nl", "q5_0", "q5_1"])
        cache_grid.addWidget(QLabel("Cache V:"), 0, 2)
        cache_grid.addWidget(self.combo_ctv, 0, 3)

        self.scroll_layout.addWidget(group_cache)

        # --- SERVER & CHAT TEMPLATE (Standard) ---
        group_server = QGroupBox("Server & Chat Options")
        server_grid = QGridLayout(group_server)
        server_grid.setContentsMargins(6, 6, 6, 6)
        server_grid.setSpacing(4)

        self.input_host = QLineEdit()
        server_grid.addWidget(QLabel("Host:"), 0, 0)
        server_grid.addWidget(self.input_host, 0, 1)

        self.spin_port = NoWheelSpinBox()
        self.spin_port.setRange(1, 65535)
        server_grid.addWidget(QLabel("Port:"), 0, 2)
        server_grid.addWidget(self.spin_port, 0, 3)

        self.check_jinja = QCheckBox("Enable Jinja template parser")
        server_grid.addWidget(self.check_jinja, 1, 0, 1, 4)

        self.combo_built_in_template = NoWheelComboBox()
        self.combo_built_in_template.addItems(["", "chatml", "gemma", "mistral", "qwen3", "llama3", "llama2", "zephyr", "phi3"])
        server_grid.addWidget(QLabel("Template (built-in):"), 2, 0)
        server_grid.addWidget(self.combo_built_in_template, 2, 1)

        self.input_chat_template = QLineEdit()
        btn_browse_template = QPushButton("...")
        btn_browse_template.clicked.connect(self.browse_template_file)
        server_grid.addWidget(QLabel("Template file:"), 3, 0)
        server_grid.addWidget(self.input_chat_template, 3, 1, 1, 1)
        server_grid.addWidget(btn_browse_template, 3, 2, 1, 2)

        self.scroll_layout.addWidget(group_server)

        # --- SPECULATIVE DECODING (Standard & Advanced) ---
        group_spec = QGroupBox("Speculative Decoding")
        spec_grid = QGridLayout(group_spec)
        spec_grid.setContentsMargins(6, 6, 6, 6)
        spec_grid.setSpacing(4)

        self.combo_spec_type = NoWheelComboBox()
        self.combo_spec_type.addItems(["none", "draft-simple", "draft-eagle3", "draft-mtp", "ngram-simple", "ngram-map-k", "ngram-map-k4v", "ngram-mod", "ngram-cache"])
        spec_grid.addWidget(QLabel("Speculative type:"), 0, 0)
        spec_grid.addWidget(self.combo_spec_type, 0, 1)

        self.spin_spec_draft = NoWheelSpinBox()
        self.spin_spec_draft.setRange(0, 100)
        spec_grid.addWidget(QLabel("Draft max:"), 0, 2)
        spec_grid.addWidget(self.spin_spec_draft, 0, 3)

        self.label_spec_draft_model = QLabel("Draft model:")
        self.input_spec_draft_model = QLineEdit()
        spec_grid.addWidget(self.label_spec_draft_model, 1, 0)
        spec_grid.addWidget(self.input_spec_draft_model, 1, 1, 1, 3)

        self.label_spec_draft_ngl = QLabel("Draft GPU:")
        self.spin_spec_draft_ngl = NoWheelSpinBox()
        self.spin_spec_draft_ngl.setRange(0, 200)
        spec_grid.addWidget(self.label_spec_draft_ngl, 2, 0)
        spec_grid.addWidget(self.spin_spec_draft_ngl, 2, 1)

        self.label_spec_draft_n_min = QLabel("Draft min:")
        self.spin_spec_draft_n_min = NoWheelSpinBox()
        self.spin_spec_draft_n_min.setRange(0, 100)
        spec_grid.addWidget(self.label_spec_draft_n_min, 2, 2)
        spec_grid.addWidget(self.spin_spec_draft_n_min, 2, 3)

        self.scroll_layout.addWidget(group_spec)

        # --- SAMPLING (Standard) ---
        group_sampling = QGroupBox("Sampling params")
        sampling_grid = QGridLayout(group_sampling)
        sampling_grid.setContentsMargins(6, 6, 6, 6)
        sampling_grid.setSpacing(4)

        self.double_temp = NoWheelDoubleSpinBox()
        self.double_temp.setRange(0.0, 2.0)
        self.double_temp.setSingleStep(0.05)
        sampling_grid.addWidget(QLabel("Temp:"), 0, 0)
        sampling_grid.addWidget(self.double_temp, 0, 1)

        self.spin_top_k = NoWheelSpinBox()
        self.spin_top_k.setRange(0, 200)
        sampling_grid.addWidget(QLabel("Top-K:"), 0, 2)
        sampling_grid.addWidget(self.spin_top_k, 0, 3)

        self.double_top_p = NoWheelDoubleSpinBox()
        self.double_top_p.setRange(0.0, 1.0)
        self.double_top_p.setSingleStep(0.05)
        sampling_grid.addWidget(QLabel("Top-P:"), 1, 0)
        sampling_grid.addWidget(self.double_top_p, 1, 1)

        self.double_penalty = NoWheelDoubleSpinBox()
        self.double_penalty.setRange(0.5, 2.0)
        self.double_penalty.setSingleStep(0.05)
        sampling_grid.addWidget(QLabel("Penalty:"), 1, 2)
        sampling_grid.addWidget(self.double_penalty, 1, 3)

        self.check_interactive = QCheckBox("Interactive mode (CLI)")
        sampling_grid.addWidget(self.check_interactive, 2, 0, 1, 2)

        self.check_color = QCheckBox("Color output (CLI)")
        sampling_grid.addWidget(self.check_color, 2, 2, 1, 2)

        self.input_custom = QLineEdit()
        sampling_grid.addWidget(QLabel("Custom:"), 3, 0)
        sampling_grid.addWidget(self.input_custom, 3, 1, 1, 3)

        self.scroll_layout.addWidget(group_sampling)

        # --- SAMPLING (Advanced) ---
        self.group_adv_sampling = QGroupBox("Sampling (Advanced)")
        adv_sampling_grid = QGridLayout(self.group_adv_sampling)
        adv_sampling_grid.setContentsMargins(6, 6, 6, 6)
        adv_sampling_grid.setSpacing(4)

        self.double_min_p = NoWheelDoubleSpinBox()
        self.double_min_p.setRange(0.0, 1.0)
        self.double_min_p.setSingleStep(0.01)
        adv_sampling_grid.addWidget(QLabel("Min-P:"), 0, 0)
        adv_sampling_grid.addWidget(self.double_min_p, 0, 1)

        self.double_dry_mult = NoWheelDoubleSpinBox()
        self.double_dry_mult.setRange(0.0, 10.0)
        self.double_dry_mult.setSingleStep(0.1)
        adv_sampling_grid.addWidget(QLabel("DRY multiplier:"), 0, 2)
        adv_sampling_grid.addWidget(self.double_dry_mult, 0, 3)

        self.double_xtc_prob = NoWheelDoubleSpinBox()
        self.double_xtc_prob.setRange(0.0, 1.0)
        self.double_xtc_prob.setSingleStep(0.05)
        adv_sampling_grid.addWidget(QLabel("XTC probability:"), 1, 0)
        adv_sampling_grid.addWidget(self.double_xtc_prob, 1, 1)

        self.double_xtc_thold = NoWheelDoubleSpinBox()
        self.double_xtc_thold.setRange(0.0, 1.0)
        self.double_xtc_thold.setSingleStep(0.05)
        adv_sampling_grid.addWidget(QLabel("XTC threshold:"), 1, 2)
        adv_sampling_grid.addWidget(self.double_xtc_thold, 1, 3)

        self.combo_mirostat = NoWheelComboBox()
        self.combo_mirostat.addItems(["0", "1", "2"])
        adv_sampling_grid.addWidget(QLabel("Mirostat:"), 2, 0)
        adv_sampling_grid.addWidget(self.combo_mirostat, 2, 1)

        self.double_mirostat_lr = NoWheelDoubleSpinBox()
        self.double_mirostat_lr.setRange(0.0, 1.0)
        self.double_mirostat_lr.setSingleStep(0.05)
        adv_sampling_grid.addWidget(QLabel("lr:"), 2, 2)
        adv_sampling_grid.addWidget(self.double_mirostat_lr, 2, 3)

        self.double_mirostat_ent = NoWheelDoubleSpinBox()
        self.double_mirostat_ent.setRange(0.0, 20.0)
        self.double_mirostat_ent.setSingleStep(0.5)
        adv_sampling_grid.addWidget(QLabel("ent:"), 3, 0)
        adv_sampling_grid.addWidget(self.double_mirostat_ent, 3, 1)

        self.scroll_layout.addWidget(self.group_adv_sampling)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Set Initial Visibility of Advanced Options
        self.check_advanced_mode.setChecked(False)
        self.toggle_advanced_visibility(Qt.CheckState.Unchecked)

        # Save & Cancel Buttons for Preset parameters
        nav_buttons = QHBoxLayout()
        nav_buttons.setSpacing(4)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("font-weight: bold;")
        btn_save.clicked.connect(self.save_preset_changes)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.discard_changes_and_exit)
        nav_buttons.addWidget(btn_save)
        nav_buttons.addWidget(btn_cancel)
        layout.addLayout(nav_buttons)

        self.stacked_widget.addWidget(preset_widget)

    # --- WIZARD AUTO-DETECTION VIEW (Page 3) ---
    def setup_wizard_view(self):
        wizard_widget = QWidget()
        layout = QVBoxLayout(wizard_widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        header_group = QGroupBox("Hardware Detection & Recommendations")
        header_grid = QGridLayout(header_group)
        header_grid.setSpacing(4)

        self.lbl_wiz_hardware = QLabel("GPU: querying...")
        header_grid.addWidget(self.lbl_wiz_hardware, 0, 0, 1, 2)

        self.lbl_wiz_arch = QLabel("Detected Arch: querying...")
        header_grid.addWidget(self.lbl_wiz_arch, 1, 0, 1, 2)

        self.lbl_wiz_vram_pct = QLabel("Model VRAM Fit: calculating...")
        header_grid.addWidget(self.lbl_wiz_vram_pct, 2, 0, 1, 2)

        layout.addWidget(header_group)

        # Propose settings
        config_group = QGroupBox("Auto-calculated parameters")
        config_grid = QGridLayout(config_group)
        config_grid.setSpacing(4)

        self.wiz_spin_threads = NoWheelSpinBox()
        self.wiz_spin_threads.setRange(1, 256)
        config_grid.addWidget(QLabel("Threads:"), 0, 0)
        config_grid.addWidget(self.wiz_spin_threads, 0, 1)

        self.wiz_spin_gpu = NoWheelSpinBox()
        self.wiz_spin_gpu.setRange(0, 999)
        config_grid.addWidget(QLabel("GPU Layers:"), 0, 2)
        config_grid.addWidget(self.wiz_spin_gpu, 0, 3)

        self.wiz_spin_ctx = NoWheelSpinBox()
        self.wiz_spin_ctx.setRange(256, 512000)
        self.wiz_spin_ctx.setSingleStep(1024)
        config_grid.addWidget(QLabel("Context Size:"), 1, 0)
        config_grid.addWidget(self.wiz_spin_ctx, 1, 1)

        self.wiz_spin_batch = NoWheelSpinBox()
        self.wiz_spin_batch.setRange(8, 8192)
        config_grid.addWidget(QLabel("Batch size:"), 1, 2)
        config_grid.addWidget(self.wiz_spin_batch, 1, 3)

        self.wiz_double_temp = NoWheelDoubleSpinBox()
        self.wiz_double_temp.setRange(0.0, 2.0)
        config_grid.addWidget(QLabel("Temp:"), 2, 0)
        config_grid.addWidget(self.wiz_double_temp, 2, 1)

        self.wiz_combo_template = NoWheelComboBox()
        self.wiz_combo_template.addItems(["", "chatml", "gemma", "mistral", "qwen3", "llama3", "llama2", "zephyr", "phi3"])
        config_grid.addWidget(QLabel("Template:"), 2, 2)
        config_grid.addWidget(self.wiz_combo_template, 2, 3)

        layout.addWidget(config_group)

        # Preset saving name
        save_group = QGroupBox("Save as New Profile")
        save_layout = QHBoxLayout(save_group)
        save_layout.setContentsMargins(6, 6, 6, 6)
        save_layout.addWidget(QLabel("Preset Name:"))
        self.input_wiz_preset_name = QLineEdit()
        save_layout.addWidget(self.input_wiz_preset_name)
        layout.addWidget(save_group)

        layout.addStretch()

        # Action layout
        btn_box = QHBoxLayout()
        btn_box.setSpacing(4)
        btn_apply = QPushButton("Save & Use")
        btn_apply.setStyleSheet("font-weight: bold;")
        btn_apply.clicked.connect(self.save_wizard_preset)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.discard_changes_and_exit)
        
        btn_box.addWidget(btn_apply)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

        self.stacked_widget.addWidget(wizard_widget)

    # --- ADVANCED SWITCH VISIBILITY ---
    def toggle_advanced_visibility(self, state):
        is_visible = (state == Qt.CheckState.Checked or state == 2)
        
        # Group Boxes
        self.group_adv_perf.setVisible(is_visible)
        self.group_rope.setVisible(is_visible)
        self.group_hw_mem.setVisible(is_visible)
        self.group_adv_sampling.setVisible(is_visible)
        
        # Speculative fields inside Standard layout
        self.label_spec_draft_model.setVisible(is_visible)
        self.input_spec_draft_model.setVisible(is_visible)
        self.label_spec_draft_ngl.setVisible(is_visible)
        self.spin_spec_draft_ngl.setVisible(is_visible)
        self.label_spec_draft_n_min.setVisible(is_visible)
        self.spin_spec_draft_n_min.setVisible(is_visible)

    # --- DYNAMIC WINDOW RESIZING ON PAGE CHANGE ---
    def on_page_changed(self, index):
        if index == 0:  # Home View
            self.resize(380, 310)
        elif index == 1:  # App Options
            self.resize(380, 220)
        elif index == 2:  # Preset Edit
            self.resize(380, 520)
        elif index == 3:  # Wizard View
            self.resize(380, 420)

    # --- ACTIONS & LOGIC ---
    def browse_llama_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Llama.cpp Root Folder")
        if dir_path:
            self.input_llama_folder.setText(dir_path)

    def browse_models_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Models Folder")
        if dir_path:
            self.input_models_path.setText(dir_path)

    def browse_template_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Chat Template File", "", "Template files (*.jinja *.txt)")
        if file_path:
            self.input_chat_template.setText(file_path)

    def update_preset_combo(self):
        self.combo_presets.blockSignals(True)
        self.combo_presets.clear()
        self.combo_presets.addItems(self.presets.keys())
        self.combo_presets.setCurrentText(self.config["selected_preset"])
        self.combo_presets.blockSignals(False)

    def update_model_combo(self):
        self.combo_models.blockSignals(True)
        self.combo_models.clear()
        models_path = self.config.get("models_path", "")
        if models_path and os.path.exists(models_path):
            try:
                files = [f for f in os.listdir(models_path) if f.endswith(".gguf")]
                self.combo_models.addItems(files)
                current_preset = self.config["selected_preset"]
                saved_model = self.presets.get(current_preset, {}).get("model", "")
                if saved_model in files:
                    self.combo_models.setCurrentText(saved_model)
            except Exception as e:
                print(f"Error listing model files: {e}")
        self.combo_models.blockSignals(False)

    def on_preset_changed(self, preset_name):
        if preset_name in self.presets:
            self.config["selected_preset"] = preset_name
            self.load_preset_to_ui(preset_name)
            self.update_model_combo()
            self.save_global_config()

    def on_model_changed(self, model_name):
        """Auto-saves selected model into current profile immediately."""
        if not model_name:
            return
        current_preset = self.config["selected_preset"]
        if current_preset in self.presets:
            if self.presets[current_preset].get("model") != model_name:
                self.presets[current_preset]["model"] = model_name
                self.save_preset_file(current_preset, self.presets[current_preset])

    def go_to_app_options(self):
        self.input_llama_folder.setText(self.config["llama_folder"])
        self.input_models_path.setText(self.config["models_path"])
        self.check_autolaunch.setChecked(self.config.get("autolaunch", False))
        self.stacked_widget.setCurrentIndex(1)

    def go_to_preset_edit(self):
        current_name = self.config["selected_preset"]
        self.input_preset_name.setText(current_name)
        self.load_preset_to_ui(current_name)
        self.stacked_widget.setCurrentIndex(2)

    def go_to_wizard(self):
        model_name = self.combo_models.currentText()
        if not model_name:
            QMessageBox.warning(self, "Warning", "Please select a model file on the main screen first.")
            return
        
        current_preset_name = self.input_preset_name.text().strip()
        if not current_preset_name:
            current_preset_name = f"Wizard-{os.path.splitext(model_name)[0][:15]}"
            
        self.input_wiz_preset_name.setText(current_preset_name)
        self.stacked_widget.setCurrentIndex(3)
        self.run_wizard_autodetect()

    def open_web_ui(self):
        preset = self.presets.get(self.config["selected_preset"], DEFAULT_PRESET_VALUES)
        host = preset.get("host", "127.0.0.1")
        port = preset.get("port", 8080)
        if not host:
            host = "127.0.0.1"
        webbrowser.open(f"http://{host}:{port}")

    # --- WIZARD AUTO-DETECTION RULES ---
    def run_wizard_autodetect(self):
        model_name = self.combo_models.currentText()
        models_dir = self.config.get("models_path", "")
        full_model_path = os.path.join(models_dir, model_name)
        
        # 1. Fetch hardware VRAM (via nvidia-smi command fallback)
        vram_free_mb = self.get_gpu_free_vram()
        if vram_free_mb > 0:
            self.lbl_wiz_hardware.setText(f"System Free VRAM: {vram_free_mb} MB")
        else:
            self.lbl_wiz_hardware.setText("GPU: Not detected (Using CPU Fallback)")

        # 2. Extract internal GGUF metadata hints using llama-cli
        cli_exe = self.get_binary_path("llama-cli.exe")
        info_text = ""
        
        # Suppress command windows flashes when frozen in PyInstaller --noconsole
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        if cli_exe and os.path.exists(full_model_path):
            try:
                result = subprocess.run(
                    [cli_exe, "--model", full_model_path, "--info"],
                    capture_output=True, text=True, timeout=12,
                    creationflags=creationflags
                )
                info_text = result.stdout + result.stderr
            except Exception:
                pass

        # Parse Architecture and trained context size
        arch = self.parse_architecture_metadata(info_text, model_name)
        ctx_max = self.parse_ctx_metadata(info_text)
        self.lbl_wiz_arch.setText(f"Detected Arch: {arch.upper()} | Trained Max Ctx: {ctx_max if ctx_max > 0 else 'Unknown'}")

        # 3. Calculate VRAM model load ratio & GPU offloading
        needed_mb = self.calculate_vram_ratio(model_name, full_model_path)
        
        if vram_free_mb > 0:
            # Deduct the default safety buffer (approx 1024MB CUDA allocation)
            effective_vram = max(0, vram_free_mb - 1024)
            fit_pct = int((effective_vram / needed_mb) * 100) if needed_mb > 0 else 0
            self.lbl_wiz_vram_pct.setText(f"Model weight size footprint: ~{needed_mb} MB | Free VRAM: {fit_pct}%")
            
            # Allocation engine
            if fit_pct >= 100:
                ngl = 99
            elif fit_pct >= 50:
                ngl = 50
            elif fit_pct >= 25:
                ngl = 20
            else:
                ngl = 0
                
            # Ctx scaling
            if effective_vram >= 12000:
                ctx, batch = 16384, 1024
            elif effective_vram >= 8000:
                ctx, batch = 8192, 512
            else:
                ctx, batch = 4096, 512
        else:
            self.lbl_wiz_vram_pct.setText(f"CPU execution only (Estimated weight size: {needed_mb} MB)")
            ngl = 0
            ctx, batch = 2048, 512

        # Cap proposed ctx size with trained metadata limits
        if ctx_max > 0 and ctx > ctx_max:
            ctx = ctx_max

        # Suggested architecture sampling templates
        temp = 0.7
        template = "chatml"
        if "gemma" in arch:
            temp = 1.0
            template = "gemma"
        elif "mistral" in arch:
            temp = 0.7
            template = "mistral"
        elif "qwen" in arch:
            temp = 0.7
            template = "qwen3"
        elif "llama" in arch:
            temp = 0.6
            template = "llama3"

        # Apply values onto screen
        self.wiz_spin_threads.setValue(6)
        self.wiz_spin_gpu.setValue(ngl)
        self.wiz_spin_ctx.setValue(ctx)
        self.wiz_spin_batch.setValue(batch)
        self.wiz_double_temp.setValue(temp)
        self.wiz_combo_template.setCurrentText(template)

    def get_gpu_free_vram(self) -> int:
        # Search nvidia-smi locally in registry locations if global resolution fails inside frozen PyInstaller bundles
        exe_path = shutil.which("nvidia-smi")
        if not exe_path:
            standard_paths = [
                r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
                r"C:\Windows\System32\nvidia-smi.exe"
            ]
            for p in standard_paths:
                if os.path.exists(p):
                    exe_path = p
                    break
        if not exe_path:
            exe_path = "nvidia-smi"

        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            result = subprocess.run(
                [exe_path, "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
                creationflags=creationflags
            )
            if result.returncode == 0:
                parts = result.stdout.strip().splitlines()
                if parts:
                    return int(parts[0].strip())
        except Exception:
            pass
        return 0

    def parse_architecture_metadata(self, info_text, filename) -> str:
        if info_text:
            kv = re.compile(r"general\.architecture[^=:\n]*[=:]\s*(\w+)|(?:print_info:\s*)?\barch\s*[=:]\s*(\w+)", re.I)
            for line in info_text.splitlines():
                m = kv.search(line)
                if m:
                    val = (m.group(1) or m.group(2) or "").lower()
                    for tag in ARCH_TAGS:
                        if tag in val:
                            return tag
        for tag in ARCH_TAGS:
            if tag in filename.lower():
                return tag
        return "generic"

    def parse_ctx_metadata(self, info_text) -> int:
        if not info_text:
            return 0
        m = re.search(r"(?:context[_-]length|n_ctx_train)\s+(?:\w+\s+)?[=:]\s*(\d+)", info_text, re.I)
        if m:
            val = int(m.group(1))
            if 512 <= val <= 262144:
                return val
        return 0

    def calculate_vram_ratio(self, name, full_path) -> int:
        try:
            file_mb = os.path.getsize(full_path) / (1024 * 1024)
        except Exception:
            file_mb = 4000  # Default estimate fallback
            
        m = _QUANT_RE.search(name)
        if m:
            key = m.group("q").lower()
            ratio_key = key if key in QUANT_VRAM_RATIO else key.replace("iq", "q")
            ratio = QUANT_VRAM_RATIO.get(ratio_key, 1.0)
        else:
            ratio = 1.0
            
        return int(file_mb * ratio * 1.15)

    def save_wizard_preset(self):
        preset_name = self.input_wiz_preset_name.text().strip()
        if not preset_name:
            QMessageBox.warning(self, "Warning", "Please provide a valid preset name.")
            return

        # Prepare config json payload (safely saving template to chat_template)
        wizard_payload = DEFAULT_PRESET_VALUES.copy()
        wizard_payload.update({
            "model": self.combo_models.currentText(),
            "threads": self.wiz_spin_threads.value(),
            "gpu_layers": self.wiz_spin_gpu.value(),
            "ctx_size": self.wiz_spin_ctx.value(),
            "batch_size": self.wiz_spin_batch.value(),
            "temp": self.wiz_double_temp.value(),
            "chat_template": self.wiz_combo_template.currentText(),
            "chat_template_file": "" # Ensure file is empty to avoid JINJA file-open crash
        })

        self.save_preset_file(preset_name, wizard_payload)
        self.load_all_presets()
        self.config["selected_preset"] = preset_name
        self.save_global_config()
        self.update_preset_combo()
        self.stacked_widget.setCurrentIndex(0)

    # --- SAVE OPTIONS ---
    def save_app_options(self):
        self.config["llama_folder"] = self.input_llama_folder.text()
        self.config["models_path"] = self.input_models_path.text()
        self.config["autolaunch"] = self.check_autolaunch.isChecked()
        self.save_global_config()
        self.update_model_combo()
        self.stacked_widget.setCurrentIndex(0)

    def save_preset_changes(self):
        preset_name = self.input_preset_name.text().strip()
        if not preset_name:
            preset_name = self.config["selected_preset"]

        current_data = self.get_ui_preset_data()
        self.save_preset_file(preset_name, current_data)
        
        self.load_all_presets()
        self.config["selected_preset"] = preset_name
        self.save_global_config()
        self.update_preset_combo()
        self.stacked_widget.setCurrentIndex(0)

    def load_preset_to_ui(self, preset_name):
        preset = self.presets.get(preset_name, DEFAULT_PRESET_VALUES)
        
        # Core Parameters
        self.spin_threads.setValue(preset.get("threads", 4))
        self.spin_gpu.setValue(preset.get("gpu_layers", 0))
        self.spin_ctx.setValue(preset.get("ctx_size", 2048))
        self.spin_batch.setValue(preset.get("batch_size", 512))
        self.check_flash_attn.setChecked(preset.get("flash_attn", False))
        self.combo_split_mode.setCurrentText(preset.get("split_mode", "none"))
        self.combo_ctk.setCurrentText(preset.get("cache_type_k", "f16"))
        self.combo_ctv.setCurrentText(preset.get("cache_type_v", "f16"))
        self.input_host.setText(preset.get("host", "127.0.0.1"))
        self.spin_port.setValue(preset.get("port", 8080))
        self.check_jinja.setChecked(preset.get("jinja", False))
        self.combo_built_in_template.setCurrentText(preset.get("chat_template", ""))
        self.input_chat_template.setText(preset.get("chat_template_file", ""))
        self.combo_spec_type.setCurrentText(preset.get("spec_type", "none"))
        self.spin_spec_draft.setValue(preset.get("spec_draft_n_max", 0))
        self.double_temp.setValue(preset.get("temp", 0.8))
        self.spin_top_k.setValue(preset.get("top_k", 40))
        self.double_top_p.setValue(preset.get("top_p", 0.9))
        self.double_penalty.setValue(preset.get("repeat_penalty", 1.1))
        self.check_interactive.setChecked(preset.get("interactive", True))
        self.check_color.setChecked(preset.get("color", True))
        self.input_custom.setText(preset.get("custom_args", ""))

        # Advanced Performance
        self.spin_threads_batch.setValue(preset.get("threads_batch", -1))
        self.input_cpu_mask.setText(preset.get("cpu_mask", ""))
        self.input_cpu_range.setText(preset.get("cpu_range", ""))
        self.combo_cpu_strict.setCurrentText(str(preset.get("cpu_strict", "0")))
        self.combo_prio.setCurrentText(str(preset.get("prio", "0")))
        self.spin_poll.setValue(preset.get("poll", 50))
        self.spin_ubatch.setValue(preset.get("ubatch_size", 512))
        self.spin_keep.setValue(preset.get("keep", 0))
        self.check_swa_full.setChecked(preset.get("swa_full", False))
        self.spin_parallel.setValue(preset.get("parallel", 1))

        # Advanced RoPE Context Scaling
        self.combo_rope_scaling.setCurrentText(preset.get("rope_scaling", "none"))
        self.double_rope_scale.setValue(preset.get("rope_scale", 1.0))
        self.double_rope_freq_base.setValue(preset.get("rope_freq_base", 0.0))
        self.double_rope_freq_scale.setValue(preset.get("rope_freq_scale", 0.0))

        # Advanced Hardware & Memory
        self.combo_numa.setCurrentText(preset.get("numa", "none"))
        self.check_mlock.setChecked(preset.get("mlock", False))
        self.check_mmap.setChecked(preset.get("mmap", True))
        self.input_device.setText(preset.get("device", ""))
        self.input_lora.setText(preset.get("lora", ""))
        self.input_lora_scaled.setText(preset.get("lora_scaled", ""))

        # Advanced Speculative Decoding
        self.input_spec_draft_model.setText(preset.get("spec_draft_model", ""))
        self.spin_spec_draft_ngl.setValue(preset.get("spec_draft_ngl", 0))
        self.spin_spec_draft_n_min.setValue(preset.get("spec_draft_n_min", 0))

        # Advanced Sampling
        self.double_min_p.setValue(preset.get("min_p", 0.05))
        self.double_xtc_prob.setValue(preset.get("xtc_prob", 0.0))
        self.double_xtc_thold.setValue(preset.get("xtc_thold", 0.1))
        self.combo_mirostat.setCurrentText(str(preset.get("mirostat", "0")))
        self.double_mirostat_lr.setValue(preset.get("mirostat_lr", 0.1))
        self.double_mirostat_ent.setValue(preset.get("mirostat_ent", 5.0))
        self.double_dry_mult.setValue(preset.get("dry_mult", 0.0))

    def get_ui_preset_data(self):
        return {
            "model": self.combo_models.currentText(),
            "threads": self.spin_threads.value(),
            "gpu_layers": self.spin_gpu.value(),
            "ctx_size": self.spin_ctx.value(),
            "batch_size": self.spin_batch.value(),
            "flash_attn": self.check_flash_attn.isChecked(),
            "split_mode": self.combo_split_mode.currentText(),
            "cache_type_k": self.combo_ctk.currentText(),
            "cache_type_v": self.combo_ctv.currentText(),
            "host": self.input_host.text(),
            "port": self.spin_port.value(),
            "jinja": self.check_jinja.isChecked(),
            "chat_template": self.combo_built_in_template.currentText(),
            "chat_template_file": self.input_chat_template.text(),
            "spec_type": self.combo_spec_type.currentText(),
            "spec_draft_n_max": self.spin_spec_draft.value(),
            "temp": self.double_temp.value(),
            "top_k": self.spin_top_k.value(),
            "top_p": self.double_top_p.value(),
            "repeat_penalty": self.double_penalty.value(),
            "interactive": self.check_interactive.isChecked(),
            "color": self.check_color.isChecked(),
            "custom_args": self.input_custom.text(),
            # Advanced Params
            "threads_batch": self.spin_threads_batch.value(),
            "cpu_mask": self.input_cpu_mask.text(),
            "cpu_range": self.input_cpu_range.text(),
            "cpu_strict": self.combo_cpu_strict.currentText(),
            "prio": self.combo_prio.currentText(),
            "poll": self.spin_poll.value(),
            "ubatch_size": self.spin_ubatch.value(),
            "keep": self.spin_keep.value(),
            "swa_full": self.check_swa_full.isChecked(),
            "parallel": self.spin_parallel.value(),
            "rope_scaling": self.combo_rope_scaling.currentText(),
            "rope_scale": self.double_rope_scale.value(),
            "rope_freq_base": self.double_rope_freq_base.value(),
            "rope_freq_scale": self.double_rope_freq_scale.value(),
            "numa": self.combo_numa.currentText(),
            "mlock": self.check_mlock.isChecked(),
            "mmap": self.check_mmap.isChecked(),
            "device": self.input_device.text(),
            "lora": self.input_lora.text(),
            "lora_scaled": self.input_lora_scaled.text(),
            "spec_draft_model": self.input_spec_draft_model.text(),
            "spec_draft_ngl": self.spin_spec_draft_ngl.value(),
            "spec_draft_n_min": self.spin_spec_draft_n_min.value(),
            "min_p": self.double_min_p.value(),
            "xtc_prob": self.double_xtc_prob.value(),
            "xtc_thold": self.double_xtc_thold.value(),
            "mirostat": self.combo_mirostat.currentText(),
            "mirostat_lr": self.double_mirostat_lr.value(),
            "mirostat_ent": self.double_mirostat_ent.value(),
            "dry_mult": self.double_dry_mult.value()
        }

    def discard_changes_and_exit(self):
        self.stacked_widget.setCurrentIndex(0)

    def get_binary_path(self, name):
        root = self.config.get("llama_folder", "")
        if not root or not os.path.exists(root):
            return None
        target = os.path.join(root, name)
        if os.path.exists(target):
            return target
        return None

    def launch_bench(self):
        bench_exe = self.get_binary_path("llama-bench.exe")
        if not bench_exe:
            print("Error: llama-bench.exe not found in specified folder.")
            return

        model_file = self.combo_models.currentText()
        if not model_file:
            print("Error: No model selected.")
            return

        models_dir = self.config.get("models_path", "")
        full_model_path = os.path.join(models_dir, model_file)

        command = f'"{bench_exe}" --model "{full_model_path}"'
        try:
            print(f"Launching Bench: {command}")
            subprocess.Popen(f'start cmd /k "{command}"', shell=True)
        except Exception as e:
            print(f"Error starting bench process: {e}")

    def launch_llama(self):
        exe = self.get_binary_path("llama-server.exe")
        is_server = True
        
        if not exe:
            exe = self.get_binary_path("llama-cli.exe")
            is_server = False

        if not exe:
            print("Error: llama-server.exe or llama-cli.exe not found in selected folder.")
            return

        model_file = self.combo_models.currentText()
        if not model_file:
            print("Error: No model selected.")
            return
            
        models_dir = self.config.get("models_path", "")
        full_model_path = os.path.join(models_dir, model_file)
        preset = self.presets.get(self.config["selected_preset"], DEFAULT_PRESET_VALUES)

        cmd = [
            f'"{exe}"',
            f'-m "{full_model_path}"',
            f'-ngl {preset.get("gpu_layers", 0)}',
            f'-c {preset.get("ctx_size", 2048)}',
            f'-b {preset.get("batch_size", 512)}',
            f'-t {preset.get("threads", 4)}',
        ]

        # Standard Performance Option mappings
        if preset.get("flash_attn", False):
            cmd.append("-fa 1")

        split_mode = preset.get("split_mode", "none")
        if split_mode != "none":
            cmd.append(f'--split-mode {split_mode}')

        cmd.append(f'-ctk {preset.get("cache_type_k", "f16")}')
        cmd.append(f'-ctv {preset.get("cache_type_v", "f16")}')

        # Advanced Performance Options mappings
        threads_b = preset.get("threads_batch", -1)
        if threads_b != -1:
            cmd.append(f'-tb {threads_b}')

        cpu_mask = preset.get("cpu_mask", "").strip()
        if cpu_mask:
            cmd.append(f'-C {cpu_mask}')

        cpu_range = preset.get("cpu_range", "").strip()
        if cpu_range:
            cmd.append(f'-Cr {cpu_range}')

        if preset.get("cpu_strict", "0") != "0":
            cmd.append("--cpu-strict 1")

        prio_val = preset.get("prio", "0")
        if prio_val != "0":
            cmd.append(f'--prio {prio_val}')

        poll_val = preset.get("poll", 50)
        if poll_val != 50:
            cmd.append(f'--poll {poll_val}')

        cmd.append(f'-ub {preset.get("ubatch_size", 512)}')
        cmd.append(f'--keep {preset.get("keep", 0)}')

        if preset.get("swa_full", False):
            cmd.append("--swa-full")

        parallel_val = preset.get("parallel", 1)
        if parallel_val != 1:
            cmd.append(f'-np {parallel_val}')

        # RoPE Scale mappings
        rope_sc = preset.get("rope_scaling", "none")
        if rope_sc != "none":
            cmd.append(f'--rope-scaling {rope_sc}')
        
        rope_sc_factor = preset.get("rope_scale", 1.0)
        if rope_sc_factor != 1.0:
            cmd.append(f'--rope-scale {rope_sc_factor}')

        rope_fb = preset.get("rope_freq_base", 0.0)
        if rope_fb != 0.0:
            cmd.append(f'--rope-freq-base {rope_fb}')

        rope_fs = preset.get("rope_freq_scale", 0.0)
        if rope_fs != 0.0:
            cmd.append(f'--rope-freq-scale {rope_fs}')

        # HW & Memory mappings
        numa_sc = preset.get("numa", "none")
        if numa_sc != "none":
            cmd.append(f'--numa {numa_sc}')

        if preset.get("mlock", False):
            cmd.append("--mlock")

        if not preset.get("mmap", True):
            cmd.append("--no-mmap")

        dev_list = preset.get("device", "").strip()
        if dev_list:
            cmd.append(f'-dev {dev_list}')

        lora_adapter = preset.get("lora", "").strip()
        if lora_adapter:
            cmd.append(f'--lora "{lora_adapter}"')

        lora_scaled_val = preset.get("lora_scaled", "").strip()
        if lora_scaled_val:
            cmd.append(f'--lora-scaled "{lora_scaled_val}"')

        # Server Engine Configuration mapping
        if is_server:
            if preset.get("jinja", False):
                cmd.append("--jinja")
            
            chat_tmpl = preset.get("chat_template", "").strip()
            if chat_tmpl:
                cmd.append(f'--chat-template {chat_tmpl}')

            chat_tmpl_file = preset.get("chat_template_file", "").strip()
            if chat_tmpl_file:
                cmd.append(f'--chat-template-file "{chat_tmpl_file}"')

            host = preset.get("host", "127.0.0.1")
            if host:
                cmd.append(f'--host {host}')
            cmd.append(f'--port {preset.get("port", 8080)}')

        # Speculative Decoding mapping
        spec_type = preset.get("spec_type", "none")
        if spec_type != "none":
            cmd.append(f'--spec-type {spec_type}')
            cmd.append(f'--spec-draft-n-max {preset.get("spec_draft_n_max", 0)}')
            
            draft_model = preset.get("spec_draft_model", "").strip()
            if draft_model:
                cmd.append(f'--spec-draft-model "{draft_model}"')
            
            draft_ngl = preset.get("spec_draft_ngl", 0)
            if draft_ngl > 0:
                cmd.append(f'--spec-draft-ngl {draft_ngl}')

            draft_n_min = preset.get("spec_draft_n_min", 0)
            if draft_n_min > 0:
                cmd.append(f'--spec-draft-n-min {draft_n_min}')

        # Sampling mappings
        cmd.append(f'--temp {preset.get("temp", 0.8)}')
        cmd.append(f'--top-k {preset.get("top_k", 40)}')
        cmd.append(f'--top-p {preset.get("top_p", 0.9)}')
        cmd.append(f'--repeat-penalty {preset.get("repeat_penalty", 1.1)}')

        # Advanced Sampling mappings
        min_p_val = preset.get("min_p", 0.05)
        if min_p_val != 0.05:
            cmd.append(f'--min-p {min_p_val}')

        xtc_p_val = preset.get("xtc_prob", 0.0)
        if xtc_p_val > 0.0:
            cmd.append(f'--xtc-probability {xtc_p_val}')
        
        xtc_t = preset.get("xtc_thold", 0.1)
        if xtc_t != 0.1:
            cmd.append(f'--xtc-threshold {xtc_t}')

        mirostat_val = preset.get("mirostat", "0")
        if mirostat_val != "0":
            cmd.append(f'--mirostat {mirostat_val}')
            cmd.append(f'--mirostat-lr {preset.get("mirostat_lr", 0.1)}')
            cmd.append(f'--mirostat-ent {preset.get("mirostat_ent", 5.0)}')

        dry_val = preset.get("dry_mult", 0.0)
        if dry_val > 0.0:
            cmd.append(f'--dry-multiplier {dry_val}')

        if not is_server:
            if preset.get("interactive", True):
                cmd.append("-i")
            if preset.get("color", True):
                cmd.append("--color")

        custom_args = preset.get("custom_args", "").strip()
        if custom_args:
            cmd.append(custom_args)

        full_command = " ".join(cmd)
        
        try:
            print(f"Launching Target Process: {full_command}")
            subprocess.Popen(f'start cmd /k "{full_command}"', shell=True)
        except Exception as e:
            print(f"Failed to start target execution process: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Tahoma", 8))
    launcher = LlamaLauncher()
    launcher.show()
    sys.exit(app.exec())