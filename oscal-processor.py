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
        self.control_details = {}

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
        ttk.Label(main_frame, text="3. Available Controls:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.controls_listbox = tk.Listbox(main_frame, height=15, selectmode=tk.SINGLE)
        self.controls_listbox.grid(row=2, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Control details display
        ttk.Label(main_frame, text="4. Control Details:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.details_text = ScrolledText(main_frame, width=70, height=10, wrap=tk.WORD)
        self.details_text.grid(row=3, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Generate button
        ttk.Button(main_frame, text="Generate Component Definition",
                  command=self.generate_component_definition).grid(row=4, column=1, sticky=tk.W, pady=10)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

        # Bind selection event
        self.controls_listbox.bind('<<ListboxSelect>>', self.show_control_details)

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
                self.extract_control_details()
                messagebox.showinfo("Info", "Catalog loaded successfully")
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
                self.populate_controls_list()
                messagebox.showinfo("Info", "Profile loaded successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load profile: {str(e)}")

    def extract_control_details(self):
        """Extract control details from catalog for quick lookup"""
        if not self.catalog_data or 'components' not in self.catalog_data or 'controls' not in self.catalog_data['components']:
            return

        self.control_details = {}

        # Find all controls in the catalog
        for control in self.catalog_data['components']['controls']:
            if 'id' in control:
                self.control_details[control['id']] = control

    def populate_controls_list(self):
        """Populate the controls listbox with control IDs from the profile"""
        if not self.profile_data or not self.catalog_data:
            return

        self.controls_listbox.delete(0, tk.END)

        # Find all controls referenced in the profile
        # This is a simplified approach - in a real OSCAL profile, you'd look for
        # controls in the "components" section with "control-implementations"
        # or similar structure
        try:
            # Try to find control implementations in the profile
            if 'components' in self.profile_data and 'control-implementations' in self.profile_data['components']:
                for impl in self.profile_data['components']['control-implementations']:
                    if 'control-ref' in impl:
                        control_id = impl['control-ref']
                        if control_id in self.control_details:
                            self.controls_listbox.insert(tk.END, control_id)
            else:
                # Fallback: list all controls from catalog if no profile controls found
                for control_id in self.control_details:
                    self.controls_listbox.insert(tk.END, control_id)
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not parse profile controls: {str(e)}")
            # Fallback to listing all catalog controls
            for control_id in self.control_details:
                self.controls_listbox.insert(tk.END, control_id)

    def show_control_details(self, event=None):
        """Display details for the selected control"""
        selection = self.controls_listbox.curselection()
        if not selection:
            return

        control_id = self.controls_listbox.get(selection)
        if control_id in self.control_details:
            control = self.control_details[control_id]
            details = f"Control ID: {control_id}\n\n"

            if 'title' in control:
                details += f"Title: {control['title']}\n\n"

            if 'description' in control:
                details += f"Description: {control['description']}\n\n"

            if 'statement' in control:
                details += f"Statement:\n{control['statement']}\n\n"

            if 'props' in control:
                details += "Properties:\n"
                for prop in control['props']:
                    if 'name' in prop and 'value' in prop:
                        details += f"  {prop['name']}: {prop['value']}\n"
                details += "\n"

            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, details)
        else:
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, f"No details found for control ID: {control_id}")

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
            if control_id in self.control_details:
                control = self.control_details[control_id]
                definition += f"        {{\n            \"id\": \"{control_id}\",\n            \"title\": \"{control.get('title', control_id)}\",\n            \"description\": \"{control.get('description', '')}\",\n            \"implementation\": {{\n                \"type\": \"software\",\n                \"version\": \"1.0\",\n                \"notes\": \"Implementation notes would go here\"\n            }}\n        }},\n"
            else:
                definition += f"        {{\n            \"id\": \"{control_id}\",\n            \"title\": \"{control_id}\",\n            \"description\": \"Control not found in catalog\"\n        }},\n"

        definition = definition.rstrip(',\n') + "\n    ]\n}\n"

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(tk.END, definition)

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
