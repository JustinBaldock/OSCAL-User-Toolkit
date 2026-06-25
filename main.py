"""
main.py
=======
This is the entry point for the OSCAL User Toolkit.

An "entry point" is the file you run to start the program.
It should be as simple as possible — just enough to get things started.

To run the app, open a terminal in the same folder as this file and type:
    python3 main.py

HOW PYTHON PACKAGES WORK
-------------------------
The folder 'oscal_user_toolkit/' is a Python package — a collection
of related modules (files). The '__init__.py' file inside it tells
Python "this folder is a package".

We import OSCALApp from the package using dot notation:
    from oscal_user_toolkit.app import OSCALApp
    
This means: "from the 'app' module inside the 'oscal_user_toolkit'
package, import the class named OSCALApp".

THE if __name__ == "__main__" GUARD
-------------------------------------
This check ensures the app only starts when you run THIS file directly.
If another file were to import from main.py, the app would NOT start
automatically. This is a Python best practice.
"""

# Import the main application class from our package
from oscal_user_toolkit.app import OSCALApp


if __name__ == "__main__":
    # Create one instance of the application (this also builds the window)
    app = OSCALApp()

    # mainloop() hands control to tkinter's event loop.
    # It waits for user actions (clicks, key presses) and responds to them.
    # The program stays here until the user closes the window.
    app.mainloop()
