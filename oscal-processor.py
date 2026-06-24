import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

class OSCALControlProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("OSCAL Control Processor")
        self.catalog_data = None
        self.profile_data = None
        self.selected_controls = []

        self.create_widgets()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Catalog selection
        ttk.Label(main_frame, text="1. Load OSCAL Catalog:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.catalog_path = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.catalog_path, width=50).grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Button(main_frame, text="Browse", command=self.load_catalog).grid(row=0, column=2, sticky=tk.W, pady=5)

        # Profile selection
        ttk.Label(main_frame, text="2. Load Control Profile:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.profile_path = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.profile_path, width=50).grid(row=1, column=1, sticky=tk.W, pady=5)
        ttk.Button(main_frame, text="Browse", command=self.load_profile).grid(row=1, column=2, sticky=tk.W, pady=5)

        # Controls selection
        ttk.Label(main_frame, text="3. Selected Controls:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.controls_listbox = tk.Listbox(main_frame, height=10, selectmode=tk.MULTIPLE)
        self.controls_listbox.grid(row=2, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Control selection buttons
        ttk.Button(main_frame, text="Add Selected", command=self.add_selected_controls).grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Button(main_frame, text="Clear All", command=self.clear_selected_controls).grid(row=3, column=1, sticky=tk.W, pady=5)

        # Component definition
        ttk.Label(main_frame, text="4. Component Definition:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.component_text = ScrolledText(main_frame, width=70, height=15)
        self.component_text.grid(row=4, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Generate button
        ttk.Button(main_frame, text="Generate Component Definition",
                  command=self.generate_component_definition).grid(row=5, column=1, sticky=tk.W, pady=10)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

    def load_catalog(self):
        file_path = filedialog.askopenfilename(
            title="Select OSCAL Catalog",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self.catalog_path.set(file_path)
            try:
                with open(file_path, 'r') as f:
                    self.catalog_data = json.load(f)
                self.populate_controls_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load catalog: {str(e)}")

    def load_profile(self):
        file_path = filedialog.askopenfilename(
            title="Select Control Profile",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self.profile_path.set(file_path)
            try:
                with open(file_path, 'r') as f:
                    self.profile_data = json.load(f)
                messagebox.showinfo("Info", "Profile loaded successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load profile: {str(e)}")

    def populate_controls_list(self):
        if not self.catalog_data:
            return

        self.controls_listbox.delete(0, tk.END)

        # Find all controls in the catalog
        if 'components' in self.catalog_data and 'controls' in self.catalog_data['components']:
            for control in self.catalog_data['components']['controls']:
                if 'id' in control:
                    self.controls_listbox.insert(tk.END, control['id'])

    def add_selected_controls(self):
        selected = self.controls_listbox.curselection()
        if not selected:
            return

        for index in selected:
            control_id = self.controls_listbox.get(index)
            if control_id not in self.selected_controls:
                self.selected_controls.append(control_id)

    def clear_selected_controls(self):
        self.selected_controls = []
        self.component_text.delete(1.0, tk.END)

    def generate_component_definition(self):
        if not self.selected_controls:
            messagebox.showwarning("Warning", "No controls selected")
            return

        if not self.catalog_data:
            messagebox.showwarning("Warning", "Please load a catalog first")
            return

        # Generate component definition
        definition = "{\n    \"component_definition\": {\n        \"name\": \"OSCAL Control Implementation\",\n        \"version\": \"1.0\",\n        \"description\": \"Implementation of selected OSCAL controls\",\n        \"controls\": [\n"

        for control_id in self.selected_controls:
            # Find the control in catalog
            control = None
            if 'components' in self.catalog_data and 'controls' in self.catalog_data['components']:
                for c in self.catalog_data['components']['controls']:
                    if c.get('id') == control_id:
                        control = c
                        break

            if control:
                definition += f"        {{\n            \"id\": \"{control_id}\",\n            \"title\": \"{control.get('title', control_id)}\",\n            \"description\": \"{control.get('description', '')}\",\n            \"implementation\": {{\n                \"type\": \"software\",\n                \"version\": \"1.0\",\n                \"notes\": \"Implementation notes would go here\"\n            }}\n        }},\n"
            else:
                definition += f"        {{\n            \"id\": \"{control_id}\",\n            \"title\": \"{control_id}\",\n            \"description\": \"Control not found in catalog\"\n        }},\n"

        definition = definition.rstrip(',\n') + "\n    ]\n}\n"

        self.component_text.delete(1.0, tk.END)
        self.component_text.insert(tk.END, definition)

        # Save option
        save = messagebox.askyesno("Save Definition", "Would you like to save this component definition?")
        if save:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if save_path:
                try:
                    with open(save_path, 'w') as f:
                        f.write(definition)
                    messagebox.showinfo("Success", "Component definition saved successfully")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save file: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = OSCALControlProcessor(root)
    root.mainloop()
