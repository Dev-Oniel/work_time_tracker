The Work Time Tracker is a desktop application developed in Python that enables users to monitor the usage time of specific applications on their computer. Featuring a modern, functional, and highly customizable interface, the program is ideal for professionals, freelancers, students, or anyone looking to manage the time spent on tasks performed in specific applications. The application combines activity tracking, timer control, and system tray integration, delivering a practical and intuitive experience.

The primary goal of the Work Time Tracker is to provide a lightweight and efficient tool to boost productivity, allowing users to track the active time spent on a selected application, with automatic inactivity detection and support for keyboard shortcuts to streamline usage. The program also includes features like compact mode, always-on-top functionality, and automatic progress saving, ensuring flexibility and convenience.

Main Features
Application-Specific Time Tracking
Allows selecting a specific application for monitoring based on open windows in the system.
Tracks time only when the selected application is active and the user is interacting with the computer, using inactivity detection (default: 10 seconds).
Modern and Customizable Interface
Graphical interface built with tkinter and styled with ttkthemes (theme: "black"), providing a clean and professional look.
Compact mode to reduce window size (180x40 pixels) and minimize screen space usage.
"Always On Top" option to keep the window above other applications.
Timer Control
Buttons to start, stop, and reset the timer, with visual feedback (green when active, red when paused).
Time display in HH:MM:SS format, updated in real-time.
Keyboard Shortcuts
Support for shortcuts for main actions:
Ctrl+Alt+E: Start the timer.
Ctrl+Alt+D: Stop the timer.
Ctrl+Alt+R: Reset the timer.
Ctrl+Alt+C: Toggle between compact and normal modes.
A help window displaying all available shortcuts.
System Tray Integration
Minimizes to the system tray with a custom icon, allowing users to restore the window or exit the program.
System tray context menu with options to show the window or quit.
Data Management
Automatic saving of accumulated time and selected application to a JSON file (tempo_uso.json).
Loads saved data upon startup, ensuring progress continuity.
Inactivity Detection
Uses pynput to monitor mouse and keyboard interactions, pausing the timer when the user is inactive for more than 10 seconds (configurable via INATIVIDADE_TEMPO).
Context Menu and Menu Bar
Right-click context menu with options to start, stop, reset, toggle compact mode, and control visibility.
Menu bar with options to select an application, view shortcuts, enable/disable "Always On Top," and toggle compact mode.
Purpose and Target Audience
The Work Time Tracker is designed for a wide range of users who need to monitor time spent on specific computer tasks. Its purpose is to offer a simple yet robust solution for:

Freelancers and Professionals: Track time spent on projects using tools like text editors, IDEs, or design software.
Students: Monitor study time in applications such as browsers, note-taking tools, or learning platforms.
Project Managers: Log time spent on collaborative or productivity tools.
General Users: Anyone interested in improving time management and understanding their application usage.
The application stands out for its ease of use, low resource consumption, and flexibility, allowing users to tailor the experience to their needs. Inactivity detection ensures only productive time is recorded, while system tray integration and keyboard shortcuts make it highly practical for daily use.

Technologies Used
Python: Main programming language.
tkinter and ttkthemes: For the graphical interface and styling.
psutil: For process monitoring (imported for potential future expansions).
pygetwindow: To retrieve information about active windows and their titles.
pynput: To monitor mouse and keyboard events.
keyboard: For global keyboard shortcut support.
pystray: For system tray integration.
PIL (Pillow): To create the system tray icon.
json and os: For managing data saved to a file.
threading: For asynchronous monitoring of windows and timer updates.
How to Use
Installation:
Clone the repository or download the app.py file.
Install dependencies:
bash

Recolher

Encapsular

Executar

Copiar
pip install tkinter ttkthemes psutil pygetwindow pynput keyboard pystray pillow
Run the program:
bash

Recolher

Encapsular

Executar

Copiar
python app.py
Operation:
Upon startup, the application displays a window with a zeroed timer.
Click "Menu" > "Select App" to choose an open application.
Use the "Start," "Stop," and "Reset" buttons or keyboard shortcuts to control the timer.
Enable compact mode or minimize to the system tray as needed.
Time is automatically saved when closing the program and loaded on the next startup.
Configuration:
Adjust the inactivity timeout (INATIVIDADE_TEMPO) in the code if needed.
Customize the compact (COMPACT_SIZE) or normal (NORMAL_SIZE) window sizes in the code.
Potential Future Improvements
Multi-Application Support: Allow tracking of multiple applications simultaneously.
Usage Reports: Generate charts or detailed reports of accumulated time.
Dynamic Settings: Interface to adjust settings like inactivity timeout without editing the code.
Customizable Themes: Support for different visual themes.
API Integration: Export data to productivity tools like Toggl or Notion.
License
The project is licensed under [insert chosen license, e.g., MIT License]. See the LICENSE file for details.

Contributions
Contributions are welcome! To suggest improvements, report bugs, or submit pull requests:

Fork the repository.
Create a feature branch (git checkout -b feature/new-functionality).
Commit your changes (git commit -m 'Add new functionality').
Push to the branch (git push origin feature/new-functionality).
Open a Pull Request.
The Work Time Tracker is a powerful and practical tool for those looking to optimize computer time management, combining simplicity, functionality, and an appealing design. Try it out and track your productivity with precision!
