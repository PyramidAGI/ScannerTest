import os
import sys
import json
import shutil
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    # Tkinter PhotoImage will still work for PNG/GIF, but fewer formats.


# -------------------------- Data Models -------------------------- #

@dataclass
class ImageData:
    original_path: str
    image_bytes: bytes = field(repr=False)
    tk_image: Any = field(default=None, repr=False)  # Thumbnail for Treeview


@dataclass
class BranchData:
    name: str
    prompt: str = ""
    image_paths: List[str] = field(default_factory=list)
    images: List[ImageData] = field(default_factory=list, repr=False)


@dataclass
class ProjectData:
    story: str = ""
    branches: List[BranchData] = field(default_factory=list)


# -------------------------- Main Application -------------------------- #

class UniversalScannerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Universal Scanner")

        # Try to set icon if you have an .ico file
        # try:
        #     self.iconbitmap("ar_glasses.ico")
        # except Exception:
        #     pass

        # Random prompts, like the C# version
        self.random_prompts = [
            "A futuristic city skyline at sunset",
            "An enchanted forest with glowing mushrooms and mythical creatures",
            "A steampunk-inspired mechanical dragon in a Victorian-era workshop",
            "A tranquil beach with crystal clear water and a lone palm tree",
            "A portrait of a wise old wizard with a long white beard, holding a crystal ball",
            "A bustling medieval marketplace with vendors, shoppers, and street performers",
            "A surreal landscape with floating islands and waterfalls that flow upwards"
        ]
        self.random = random.Random()

        # Data
        self.branches: List[BranchData] = []
        self.node_data: Dict[str, Any] = {}  # tree item -> BranchData or ImageData
        self.current_branch: Optional[BranchData] = None

        # Keep references to PhotoImages to avoid GC
        self.image_refs: List[ImageTk.PhotoImage] = []

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # -------------------------- UI Construction -------------------------- #

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        # Project tab
        self.project_frame = ttk.Frame(notebook)
        notebook.add(self.project_frame, text="Project")

        # Quantities tab
        self.quantities_frame = ttk.Frame(notebook)
        notebook.add(self.quantities_frame, text="Quantities")

        self._build_project_tab()
        self._build_quantities_tab()

    def _build_project_tab(self):
        # Main layout: left tree + buttons, right text/image
        self.project_frame.columnconfigure(1, weight=1)
        self.project_frame.rowconfigure(0, weight=1)

        # Left: Tree + buttons
        left_frame = ttk.Frame(self.project_frame, padding=5)
        left_frame.grid(row=0, column=0, sticky="nsew")

        tree_label = ttk.Label(left_frame, text="Branches & Images")
        tree_label.pack(anchor="w")

        self.tree = ttk.Treeview(left_frame, show="tree")
        self.tree.pack(fill="both", expand=True, pady=(2, 5))

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill="x")

        add_branch_btn = ttk.Button(btn_frame, text="Add Branch", command=self.add_branch)
        add_branch_btn.pack(side="left", padx=2, pady=2)

        upload_image_btn = ttk.Button(btn_frame, text="Upload Image(s)", command=self.upload_images)
        upload_image_btn.pack(side="left", padx=2, pady=2)

        # Right side: story, prompt, image, project name/save/load
        right_frame = ttk.Frame(self.project_frame, padding=5)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)
        right_frame.rowconfigure(2, weight=1)

        # Story
        story_label = ttk.Label(right_frame, text="Story:")
        story_label.grid(row=0, column=0, sticky="w")
        self.story_text = tk.Text(right_frame, height=5)
        self.story_text.grid(row=1, column=0, sticky="nsew", pady=(0, 5))

        # Prompt
        prompt_label = ttk.Label(right_frame, text="Prompt for selected branch:")
        prompt_label.grid(row=2, column=0, sticky="w")
        self.prompt_text = tk.Text(right_frame, height=5)
        self.prompt_text.grid(row=3, column=0, sticky="nsew", pady=(0, 5))

        # Image preview
        image_label = ttk.Label(right_frame, text="Selected image preview:")
        image_label.grid(row=4, column=0, sticky="w", pady=(5, 0))

        self.image_preview = ttk.Label(right_frame, relief="sunken")
        self.image_preview.grid(row=5, column=0, sticky="nsew")
        right_frame.rowconfigure(5, weight=1)

        # Project name + save/load
        bottom_frame = ttk.Frame(right_frame)
        bottom_frame.grid(row=6, column=0, sticky="ew", pady=(5, 0))
        bottom_frame.columnconfigure(1, weight=1)

        name_label = ttk.Label(bottom_frame, text="Project name:")
        name_label.grid(row=0, column=0, sticky="w")

        self.project_name_var = tk.StringVar()
        self.project_name_entry = ttk.Entry(bottom_frame, textvariable=self.project_name_var)
        self.project_name_entry.grid(row=0, column=1, sticky="ew", padx=5)

        save_btn = ttk.Button(bottom_frame, text="Save Project", command=self.save_project)
        save_btn.grid(row=0, column=2, padx=2)

        load_btn = ttk.Button(bottom_frame, text="Load Project", command=self.load_project)
        load_btn.grid(row=0, column=3, padx=2)

    def _build_quantities_tab(self):
        # Layout: main panel with Text on left, buttons on right, export at bottom
        self.quantities_frame.columnconfigure(0, weight=1)
        self.quantities_frame.rowconfigure(0, weight=1)

        main_panel = ttk.Frame(self.quantities_frame)
        main_panel.grid(row=0, column=0, sticky="nsew")
        main_panel.columnconfigure(0, weight=1)
        main_panel.rowconfigure(0, weight=1)

        text_frame = ttk.Frame(main_panel)
        text_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        self.quantities_text = tk.Text(
            text_frame,
            wrap="none",
            font=("Courier New", 10),
            state="normal"
        )
        self.quantities_text.grid(row=0, column=0, sticky="nsew")

        # Scrollbars
        yscroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.quantities_text.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.quantities_text.configure(yscrollcommand=yscroll.set)

        xscroll = ttk.Scrollbar(text_frame, orient="horizontal", command=self.quantities_text.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.quantities_text.configure(xscrollcommand=xscroll.set)

        # When clicking a line, append it to prompt
        self.quantities_text.bind("<Button-1>", self.on_quantities_click)

        # Right button panel
        button_panel = ttk.Frame(main_panel)
        button_panel.grid(row=0, column=1, sticky="ns", padx=5, pady=5)

        refresh_btn = ttk.Button(button_panel, text="Refresh", command=self.refresh_quantities)
        refresh_btn.pack(fill="x", pady=2)

        load_csv_btn = ttk.Button(button_panel, text="Load CSV", command=self.load_quantities_csv)
        load_csv_btn.pack(fill="x", pady=2)

        export_btn = ttk.Button(button_panel, text="Export Quantities", command=self.export_quantities)
        export_btn.pack(fill="x", pady=(20, 2))

    # -------------------------- Tree / Branch logic -------------------------- #

    def add_branch(self):
        # Ask for branch name
        default_name = f"Branch {len(self.branches) + 1}"
        branch_name = simpledialog.askstring("Add Branch", "Enter branch name:", initialvalue=default_name)
        if not branch_name:
            return

        prompt = self.random.choice(self.random_prompts)
        branch = BranchData(name=branch_name, prompt=prompt)
        self.branches.append(branch)

        item_id = self.tree.insert("", "end", text=branch_name)
        self.node_data[item_id] = branch

        # Auto-select the new branch
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.set_current_branch(branch)
        self.update_prompt_text_from_branch(branch)

    def upload_images(self):
        # Require a selected node; use its root-level parent as branch node
        selected = self._get_selected_item()
        if not selected:
            messagebox.showinfo("Upload Images", "Please select a branch to upload images to.")
            return

        branch_item = self._get_branch_item_for(selected)
        branch_data = self.node_data.get(branch_item)
        if not isinstance(branch_data, BranchData):
            messagebox.showinfo("Upload Images", "Please select a branch to upload images to.")
            return

        # Count existing images
        existing_images_count = len(branch_data.images)

        filetypes = [
            ("Image files", "*.jpg *.jpeg *.png *.gif *.bmp"),
            ("All files", "*.*"),
        ]
        filenames = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=filetypes
        )
        if not filenames:
            return

        if existing_images_count + len(filenames) > 2:
            messagebox.showerror("Image Limit", "You can only add up to two images per branch.")
            return

        image_counter = existing_images_count + 1

        for fname in filenames:
            try:
                with open(fname, "rb") as f:
                    img_bytes = f.read()
            except Exception as e:
                messagebox.showerror("Error", f"Could not read image {fname}:\n{e}")
                continue

            img_data = ImageData(original_path=fname, image_bytes=img_bytes)
            branch_data.images.append(img_data)

            # Create thumbnail image for Treeview
            thumb = self._create_thumbnail(img_bytes)
            img_data.tk_image = thumb
            if thumb is not None:
                self.image_refs.append(thumb)

            image_item = self.tree.insert(
                branch_item,
                "end",
                text=f"Image {image_counter}",
                image=thumb if thumb is not None else ""
            )
            self.node_data[image_item] = img_data
            image_counter += 1

        self.tree.item(branch_item, open=True)

    def on_tree_select(self, event=None):
        # Persist current branch's prompt before switching
        if self.current_branch is not None:
            self.current_branch.prompt = self.prompt_text.get("1.0", "end").rstrip("\n")

        selected = self._get_selected_item()
        if not selected:
            return

        # New branch for the newly selected item
        branch_item = self._get_branch_item_for(selected)
        branch_data = self.node_data.get(branch_item)
        if isinstance(branch_data, BranchData):
            self.set_current_branch(branch_data)
            self.update_prompt_text_from_branch(branch_data)
        else:
            self.current_branch = None
            self.prompt_text.delete("1.0", "end")

        # Image preview
        node_obj = self.node_data.get(selected)
        if isinstance(node_obj, ImageData):
            self._show_image_preview(node_obj.image_bytes)
        else:
            # Clear preview
            self.image_preview.configure(image="")
            self.image_preview.image = None

    def set_current_branch(self, branch: Optional[BranchData]):
        self.current_branch = branch

    def update_prompt_text_from_branch(self, branch: BranchData):
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", branch.prompt or "")

    def _get_selected_item(self) -> Optional[str]:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _get_branch_item_for(self, item_id: str) -> str:
        # Climb up parents until root level (branch)
        parent = self.tree.parent(item_id)
        while parent:
            item_id = parent
            parent = self.tree.parent(item_id)
        return item_id

    # -------------------------- Image Helpers -------------------------- #

    def _create_thumbnail(self, image_bytes: bytes, size=(24, 24)):
        if not PIL_AVAILABLE:
            try:
                # Fallback: PhotoImage from memory via temp file (minimal)
                # but this may not support all formats.
                import tempfile
                tmp = tempfile.NamedTemporaryFile(delete=False)
                tmp.write(image_bytes)
                tmp.close()
                img = tk.PhotoImage(file=tmp.name)
                os.unlink(tmp.name)
                return img
            except Exception:
                return None

        from io import BytesIO
        try:
            im = Image.open(BytesIO(image_bytes))
            im.thumbnail(size)
            return ImageTk.PhotoImage(im)
        except Exception:
            return None

    def _show_image_preview(self, image_bytes: bytes, max_size=(400, 300)):
        if not PIL_AVAILABLE:
            # Minimal fallback: same as thumbnail
            img = self._create_thumbnail(image_bytes, max_size)
            if img:
                self.image_preview.configure(image=img)
                self.image_preview.image = img
            return

        from io import BytesIO
        try:
            im = Image.open(BytesIO(image_bytes))
            im.thumbnail(max_size)
            img = ImageTk.PhotoImage(im)
            self.image_preview.configure(image=img)
            self.image_preview.image = img
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not display image:\n{e}")

    # -------------------------- Save / Load Project -------------------------- #

    @staticmethod
    def _desktop_scanner_folder() -> str:
        home = os.path.expanduser("~")
        return os.path.join(home, "Desktop", "Scanner")

    def save_project(self):
        # Persist current branch prompt
        if self.current_branch is not None:
            self.current_branch.prompt = self.prompt_text.get("1.0", "end").rstrip("\n")

        project_name = self.project_name_var.get().strip()
        if not project_name:
            project_name = simpledialog.askstring("Save Project", "Enter project name:", initialvalue="MyProject")
            if not project_name:
                return
            self.project_name_var.set(project_name)

        base = self._desktop_scanner_folder()
        project_path = os.path.join(base, project_name)

        if os.path.exists(project_path):
            messagebox.showerror("Save Error", "Project already exists. Please use another name.")
            return

        os.makedirs(project_path, exist_ok=True)

        # Prepare data
        proj_data = ProjectData()
        proj_data.story = self.story_text.get("1.0", "end").rstrip("\n")

        # Branches
        for branch in self.branches:
            # Reset image paths and copy images into project folder
            branch.image_paths = []
            for img_data in branch.images:
                new_name = os.path.basename(img_data.original_path)
                new_path = os.path.join(project_path, new_name)
                try:
                    shutil.copy2(img_data.original_path, new_path)
                except Exception as e:
                    messagebox.showerror(
                        "Image Copy Error",
                        f"Could not copy {img_data.original_path}:\n{e}"
                    )
                    continue
                branch.image_paths.append(new_name)
            proj_data.branches.append(branch)

        json_obj = {
            "Story": proj_data.story,
            "Branches": [
                {
                    "Name": b.name,
                    "Prompt": b.prompt,
                    "ImagePaths": b.image_paths,
                }
                for b in proj_data.branches
            ]
        }

        json_path = os.path.join(project_path, "project.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_obj, f, indent=4)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not write project.json:\n{e}")
            return

        messagebox.showinfo("Save Successful", f"Project saved to:\n{project_path}")

    def load_project(self):
        base = self._desktop_scanner_folder()
        os.makedirs(base, exist_ok=True)

        filename = filedialog.askopenfilename(
            title="Load Project",
            initialdir=base,
            filetypes=[("Project files", "*.json"), ("All files", "*.*")]
        )
        if not filename:
            return

        project_path = os.path.dirname(filename)
        project_name = os.path.basename(project_path)
        self.project_name_var.set(project_name)

        try:
            with open(filename, "r", encoding="utf-8") as f:
                json_obj = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not read project file:\n{e}")
            return

        self.clear_project_data()

        story = json_obj.get("Story", "")
        self.story_text.insert("1.0", story)

        branches_json = json_obj.get("Branches", [])
        for b in branches_json:
            name = b.get("Name", "Branch")
            prompt = b.get("Prompt", "")
            image_paths = b.get("ImagePaths", [])

            branch = BranchData(name=name, prompt=prompt, image_paths=image_paths)
            self.branches.append(branch)

            branch_item = self.tree.insert("", "end", text=name)
            self.node_data[branch_item] = branch

            # Load images from disk
            image_counter = 1
            for img_name in image_paths:
                img_path = os.path.join(project_path, img_name)
                if not os.path.exists(img_path):
                    continue
                try:
                    with open(img_path, "rb") as f:
                        img_bytes = f.read()
                except Exception:
                    continue

                img_data = ImageData(original_path=img_path, image_bytes=img_bytes)
                branch.images.append(img_data)

                thumb = self._create_thumbnail(img_bytes)
                img_data.tk_image = thumb
                if thumb is not None:
                    self.image_refs.append(thumb)

                item_id = self.tree.insert(
                    branch_item,
                    "end",
                    text=f"Image {image_counter}",
                    image=thumb if thumb is not None else ""
                )
                self.node_data[item_id] = img_data
                image_counter += 1

            self.tree.item(branch_item, open=True)

    def clear_project_data(self):
        # Clear image preview
        self.image_preview.configure(image="")
        self.image_preview.image = None

        # Clear tree, mappings, branches
        self.tree.delete(*self.tree.get_children())
        self.node_data.clear()
        self.branches.clear()
        self.current_branch = None
        self.image_refs.clear()

        # Clear text fields
        self.prompt_text.delete("1.0", "end")
        self.story_text.delete("1.0", "end")

    # -------------------------- Quantities Tab Logic -------------------------- #

    def refresh_quantities(self):
        # Desktop\scanner\quantities.txt (case-insensitive on Windows but we mimic original)
        base = self._desktop_scanner_folder()
        file_path = os.path.join(base, "quantities.txt")

        self.quantities_text.config(state="normal")
        self.quantities_text.delete("1.0", "end")

        if not os.path.exists(file_path):
            messagebox.showerror("File Not Found", f"The file was not found at:\n{file_path}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while reading the file:\n{e}")
            return

        formatted = self._format_csv_like_text(content)
        self.quantities_text.insert("1.0", formatted)
        self.quantities_text.config(state="normal")

    def load_quantities_csv(self):
        filename = filedialog.askopenfilename(
            title="Load Quantities from CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return

        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Error reading CSV file:\n{e}")
            return

        formatted = self._format_csv_like_text(content)
        self.quantities_text.config(state="normal")
        self.quantities_text.delete("1.0", "end")
        self.quantities_text.insert("1.0", formatted)

    def _format_csv_like_text(self, content: str) -> str:
        lines = [ln for ln in content.splitlines() if ln.strip()]
        out_lines = []
        for ln in lines:
            fields = [f.strip() for f in ln.split(",") if f.strip() != ""]
            padded = "".join(f.ljust(15) for f in fields)
            out_lines.append(padded)
        return "\n".join(out_lines) + ("\n" if out_lines else "")

    def export_quantities(self):
        txt = self.quantities_text.get("1.0", "end")
        if not txt.strip():
            messagebox.showinfo("Export Quantities", "Nothing to export.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export Quantities",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All files", "*.*")]
        )
        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(txt)
        except Exception as e:
            messagebox.showerror("Error", f"Could not export quantities:\n{e}")
            return

        messagebox.showinfo("Export Complete", "Quantities exported successfully!")

    def on_quantities_click(self, event):
        # Determine clicked line and append to prompt_text
        index = self.quantities_text.index(f"@{event.x},{event.y}")
        line_no = index.split(".")[0]
        line_text = self.quantities_text.get(f"{line_no}.0", f"{line_no}.end").rstrip()
        if line_text.strip():
            self.prompt_text.insert("end", line_text + "\n")
            self.prompt_text.see("end")

    # -------------------------- General Helpers -------------------------- #

    def on_close(self):
        # Equivalent to FormClosed -> ClearProjectData
        self.clear_project_data()
        self.destroy()


# -------------------------- Entry Point -------------------------- #

if __name__ == "__main__":
    app = UniversalScannerApp()
    app.geometry("1000x700")
    app.mainloop()
