import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext

class OSCALCatalogViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("OSCAL Catalog Viewer")
        self.catalog_data = None
        self.current_control = None

        self.create_widgets()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # File selection
        ttk.Label(main_frame, text="OSCAL Catalog File:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.file_path = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.file_path, width=60).grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Button(main_frame, text="Browse", command=self.load_catalog).grid(row=0, column=2, sticky=tk.W, pady=5)

        # Control selection
        ttk.Label(main_frame, text="Control ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.control_id = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.control_id, width=30).grid(row=1, column=1, sticky=tk.W, pady=5)
        ttk.Button(main_frame, text="View Control", command=self.view_control).grid(row=1, column=2, sticky=tk.W, pady=5)

        # Search functionality
        ttk.Label(main_frame, text="Search Controls:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.search_term = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.search_term, width=30).grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Button(main_frame, text="Search", command=self.search_controls).grid(row=2, column=2, sticky=tk.W, pady=5)

        # Controls list
        ttk.Label(main_frame, text="Available Controls:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.controls_listbox = tk.Listbox(main_frame, height=15)
        self.controls_listbox.grid(row=3, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Control details display
        ttk.Label(main_frame, text="Control Details:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.details_text = scrolledtext.ScrolledText(main_frame, width=80, height=20, wrap=tk.WORD)
        self.details_text.grid(row=4, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

        # Bind listbox selection
        self.controls_listbox.bind('<<ListboxSelect>>', self.show_selected_control)

    def load_catalog(self):
        file_path = filedialog.askopenfilename(
            title="Select OSCAL Catalog",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self.file_path.set(file_path)
            try:
                with open(file_path, 'r') as f:
                    self.catalog_data = json.load(f)
                self.populate_controls_list()
                messagebox.showinfo("Success", "Catalog loaded successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load catalog: {str(e)}")

    def populate_controls_list(self):
        if not self.catalog_data or 'components' not in self.catalog_data or 'controls' not in self.catalog_data['components']:
            self.controls_listbox.delete(0, tk.END)
            return

        self.controls_listbox.delete(0, tk.END)

        # Find all controls in the catalog
        for control in self.catalog_data['components']['controls']:
            if 'id' in control:
                self.controls_listbox.insert(tk.END, control['id'])

    def view_control(self):
        control_id = self.control_id.get().strip()
        if not control_id:
            messagebox.showwarning("Warning", "Please enter a control ID")
            return

        if not self.catalog_data:
            messagebox.showwarning("Warning", "Please load a catalog first")
            return

        # Search for the control
        found = False
        for control in self.catalog_data['components']['controls']:
            if 'id' in control and control['id'] == control_id:
                self.show_control_details(control)
                found = True
                break

        if not found:
            messagebox.showwarning("Warning", f"Control ID '{control_id}' not found")

    def search_controls(self):
        search_term = self.search_term.get().strip().lower()
        if not search_term:
            messagebox.showwarning("Warning", "Please enter a search term")
            return

        if not self.catalog_data:
            messagebox.showwarning("Warning", "Please load a catalog first")
            return

        self.controls_listbox.delete(0, tk.END)

        for control in self.catalog_data['components']['controls']:
            if 'id' in control:
                if search_term in control['id'].lower():
                    self.controls_listbox.insert(tk.END, control['id'])

    def show_selected_control(self, event):
        selection = self.controls_listbox.curselection()
        if not selection:
            return

        control_id = self.controls_listbox.get(selection)
        self.control_id.set(control_id)
        self.view_control()

    def show_control_details(self, control):
        self.details_text.delete(1.0, tk.END)

        # Basic control information
        details = f"Control ID: {control.get('id', 'N/A')}\n\n"

        if 'title' in control:
            details += f"Title: {control['title']}\n\n"

        if 'description' in control:
            details += f"Description: {control['description']}\n\n"

        # Process parts (statements, prose, etc.)
        if 'parts' in control:
            details += "Control Statement:\n\n"
            for part in control['parts']:
                if 'prose' in part:
                    details += f"{part.get('id', '')}: {part['prose']}\n\n"
                elif 'name' in part and 'prose' in part:
                    details += f"{part['name']}:\n{part['prose']}\n\n"

        # Properties
        if 'props' in control:
            details += "\nProperties:\n"
            for prop in control['props']:
                if 'name' in prop and 'value' in prop:
                    details += f"  {prop['name']}: {prop['value']}\n"

        self.details_text.insert(tk.END, details)
        self.current_control = control

if __name__ == "__main__":
    root = tk.Tk()
    app = OSCALCatalogViewer(root)
    root.mainloop()
