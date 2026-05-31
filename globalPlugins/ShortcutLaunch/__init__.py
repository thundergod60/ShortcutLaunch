# shortcutLaunch/__init__.py

import os
import subprocess
import webbrowser
import json
import wx
import gui
import ui
import globalVars
import globalPluginHandler
import addonHandler
from scriptHandler import script
from logHandler import log

addonHandler.initTranslation()

CONFIG_FILE = os.path.join(globalVars.appArgs.configPath, "shortcutLaunch.json")

def loadShortcuts():
    """Loads saved shortcuts and upgrades older string-only formats to the new dictionary format."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for key, value in data.items():
                    if isinstance(value, str):
                        data[key] = {
                            "type": "Program/File",
                            "target": value,
                            "workdir": os.path.expanduser("~")
                        }
                return data
        except Exception as e:
            log.error(f"ShortcutLaunch: Failed to load shortcuts: {e}")
    return {}

def saveShortcuts(shortcuts):
    """Saves shortcuts to the JSON config file."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(shortcuts, f, indent=4)
    except Exception as e:
        log.error(f"ShortcutLaunch: Failed to save shortcuts: {e}")

class ShortcutEditorDialog(wx.Dialog):
    """The dialog used to add OR edit a shortcut."""
    def __init__(self, parent, title=_("Add New Shortcut"), name="", data=None):
        super(ShortcutEditorDialog, self).__init__(parent, title=title)
        
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        
        # 1. Shortcut Name
        mainSizer.Add(wx.StaticText(self, label=_("Shortcut &Name:")), 0, wx.ALL, 5)
        self.nameCtrl = wx.TextCtrl(self)
        mainSizer.Add(self.nameCtrl, 0, wx.EXPAND | wx.ALL, 5)
        
        # 2. Radio buttons for Shortcut Type
        self.types = [_("Program/File"), _("Folder"), _("URL"), _("Command")]
        self.typeRadio = wx.RadioBox(
            self, label=_("Shortcut &Type:"), 
            choices=self.types, majorDimension=1, style=wx.RA_SPECIFY_COLS
        )
        self.typeRadio.Bind(wx.EVT_RADIOBOX, self.onTypeChange)
        mainSizer.Add(self.typeRadio, 0, wx.EXPAND | wx.ALL, 5)
        
        # 3. Target Field
        mainSizer.Add(wx.StaticText(self, label=_("&Target (Path, URL, or Command):")), 0, wx.ALL, 5)
        self.targetCtrl = wx.TextCtrl(self)
        mainSizer.Add(self.targetCtrl, 0, wx.EXPAND | wx.ALL, 5)
        
        # Browse Buttons for Target
        browseSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btnBrowseFile = wx.Button(self, label=_("Browse &File..."))
        self.btnBrowseFile.Bind(wx.EVT_BUTTON, self.onBrowseFile)
        browseSizer.Add(self.btnBrowseFile, 0, wx.ALL, 5)
        
        self.btnBrowseFolder = wx.Button(self, label=_("Browse F&older..."))
        self.btnBrowseFolder.Bind(wx.EVT_BUTTON, self.onBrowseFolder)
        browseSizer.Add(self.btnBrowseFolder, 0, wx.ALL, 5)
        
        mainSizer.Add(browseSizer, 0, wx.EXPAND)

        # 4. Working Directory Field (For Commands)
        mainSizer.Add(wx.StaticText(self, label=_("&Working Directory (For Commands):")), 0, wx.ALL, 5)
        self.workdirCtrl = wx.TextCtrl(self, value=os.path.expanduser("~"))
        mainSizer.Add(self.workdirCtrl, 0, wx.EXPAND | wx.ALL, 5)
        
        self.btnBrowseWorkdir = wx.Button(self, label=_("Browse &Working Dir..."))
        self.btnBrowseWorkdir.Bind(wx.EVT_BUTTON, self.onBrowseWorkdir)
        mainSizer.Add(self.btnBrowseWorkdir, 0, wx.ALL, 5)
        
        # Populate data if we are editing an existing shortcut
        if name and data:
            self.nameCtrl.SetValue(name)
            self.targetCtrl.SetValue(data.get("target", ""))
            
            sType = data.get("type", "Program/File")
            if sType in self.types:
                self.typeRadio.SetSelection(self.types.index(sType))
                
            self.workdirCtrl.SetValue(data.get("workdir", os.path.expanduser("~")))
        
        # Trigger UI update for browse buttons based on current selection
        self.onTypeChange(None)
        
        # Standard OK / Cancel buttons
        btnSizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        mainSizer.Add(btnSizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizerAndFit(mainSizer)

    def onTypeChange(self, evt):
        selection = self.typeRadio.GetSelection()
        
        self.btnBrowseFile.Disable()
        self.btnBrowseFolder.Disable()
        self.workdirCtrl.Disable()
        self.btnBrowseWorkdir.Disable()
        
        if selection == 0:   # Program/File
            self.btnBrowseFile.Enable()
        elif selection == 1: # Folder
            self.btnBrowseFolder.Enable()
        elif selection == 3: # Command
            self.workdirCtrl.Enable()
            self.btnBrowseWorkdir.Enable()

    def onBrowseFile(self, evt):
        with wx.FileDialog(self, _("Select a file"), style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
            if fd.ShowModal() == wx.ID_OK:
                self.targetCtrl.SetValue(fd.GetPath())
                
    def onBrowseFolder(self, evt):
        with wx.DirDialog(self, _("Select a folder"), style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dd:
            if dd.ShowModal() == wx.ID_OK:
                self.targetCtrl.SetValue(dd.GetPath())

    def onBrowseWorkdir(self, evt):
        with wx.DirDialog(self, _("Select working directory"), style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dd:
            if dd.ShowModal() == wx.ID_OK:
                self.workdirCtrl.SetValue(dd.GetPath())

class LauncherDialog(wx.Dialog):
    def __init__(self, parent):
        super(LauncherDialog, self).__init__(parent, title=_("ShortcutLaunch"))
        self.shortcuts = loadShortcuts()
        
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        
        # --- NEW: Search and Filter Sizer ---
        filterSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Text Search Box
        filterSizer.Add(wx.StaticText(self, label=_("S&earch:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.searchCtrl = wx.TextCtrl(self)
        self.searchCtrl.Bind(wx.EVT_TEXT, self.onFilterChange)
        filterSizer.Add(self.searchCtrl, 1, wx.EXPAND | wx.ALL, 5)
        
        # Type Dropdown Filter
        self.filterTypes = [_("All"), _("Program/File"), _("Folder"), _("URL"), _("Command")]
        filterSizer.Add(wx.StaticText(self, label=_("&Filter by:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.typeChoice = wx.Choice(self, choices=self.filterTypes)
        self.typeChoice.SetSelection(0)
        self.typeChoice.Bind(wx.EVT_CHOICE, self.onFilterChange)
        filterSizer.Add(self.typeChoice, 0, wx.EXPAND | wx.ALL, 5)
        
        mainSizer.Add(filterSizer, 0, wx.EXPAND)
        
        # --- ListBox ---
        mainSizer.Add(wx.StaticText(self, label=_("S&hortcuts:")), 0, wx.ALL, 5)
        self.listCtrl = wx.ListBox(self, style=wx.LB_SINGLE)
        self.listCtrl.Bind(wx.EVT_LISTBOX_DCLICK, self.onLaunchShortcut)
        mainSizer.Add(self.listCtrl, 1, wx.EXPAND | wx.ALL, 5)
        
        # Initialize list based on empty search/filter
        self.refreshList()
        
        # --- Bottom Buttons ---
        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btnLaunch = wx.Button(self, wx.ID_OK, label=_("&Launch"))
        self.btnLaunch.SetDefault() 
        btnSizer.Add(self.btnLaunch, 0, wx.ALL, 5)
        
        self.btnAdd = wx.Button(self, label=_("&Add..."))
        self.btnAdd.Bind(wx.EVT_BUTTON, self.onAdd)
        btnSizer.Add(self.btnAdd, 0, wx.ALL, 5)
        
        self.btnEdit = wx.Button(self, label=_("&Edit..."))
        self.btnEdit.Bind(wx.EVT_BUTTON, self.onEdit)
        btnSizer.Add(self.btnEdit, 0, wx.ALL, 5)
        
        self.btnDelete = wx.Button(self, label=_("&Delete"))
        self.btnDelete.Bind(wx.EVT_BUTTON, self.onDelete)
        btnSizer.Add(self.btnDelete, 0, wx.ALL, 5)
        
        self.btnCancel = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
        btnSizer.Add(self.btnCancel, 0, wx.ALL, 5)
        
        mainSizer.Add(btnSizer, 0, wx.ALIGN_RIGHT)
        self.SetSizerAndFit(mainSizer)
        
        # Start focus on the search box for fast typing, or the list if you prefer
        self.searchCtrl.SetFocus()

    def onFilterChange(self, evt):
        """Triggered when user types in search or changes the dropdown."""
        self.refreshList()

    def refreshList(self, select_name=None):
        """Filters, sorts, and populates the listbox."""
        search_text = self.searchCtrl.GetValue().lower()
        selected_type = self.filterTypes[self.typeChoice.GetSelection()]
        
        filtered_keys = []
        for name, data in self.shortcuts.items():
            # Filter by Text Search
            if search_text and search_text not in name.lower():
                continue
            
            # Filter by Category Type
            if selected_type != _("All") and data.get("type", "Auto") != selected_type:
                continue
                
            filtered_keys.append(name)

        sorted_keys = sorted(filtered_keys, key=lambda x: x.lower())
        
        # Remember currently selected item before refreshing
        current_selection = self.listCtrl.GetStringSelection()
        if select_name:
            current_selection = select_name
            
        self.listCtrl.SetItems(sorted_keys)
        
        # Try to restore selection, otherwise select first item
        if current_selection in sorted_keys:
            self.listCtrl.SetStringSelection(current_selection)
        elif self.listCtrl.GetCount() > 0:
            self.listCtrl.SetSelection(0)

    def onLaunchShortcut(self, evt):
        self.EndModal(wx.ID_OK)

    def onAdd(self, evt):
        dlg = ShortcutEditorDialog(self, title=_("Add New Shortcut"))
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.nameCtrl.GetValue().strip()
            target = dlg.targetCtrl.GetValue().strip()
            sType = dlg.types[dlg.typeRadio.GetSelection()]
            workdir = dlg.workdirCtrl.GetValue().strip()
            
            if not name or not target:
                ui.message(_("Name and Target cannot be empty."))
            else:
                self.shortcuts[name] = {
                    "type": sType,
                    "target": target,
                    "workdir": workdir if workdir else os.path.expanduser("~")
                }
                saveShortcuts(self.shortcuts)
                self.refreshList(name)
                ui.message(_("Shortcut saved"))
        dlg.Destroy()
        self.listCtrl.SetFocus()

    def onEdit(self, evt):
        selection = self.listCtrl.GetSelection()
        if selection == wx.NOT_FOUND:
            ui.message(_("No shortcut selected"))
            return
            
        old_name = self.listCtrl.GetString(selection)
        data = self.shortcuts.get(old_name)
        
        dlg = ShortcutEditorDialog(self, title=_("Edit Shortcut"), name=old_name, data=data)
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.nameCtrl.GetValue().strip()
            target = dlg.targetCtrl.GetValue().strip()
            sType = dlg.types[dlg.typeRadio.GetSelection()]
            workdir = dlg.workdirCtrl.GetValue().strip()
            
            if not new_name or not target:
                ui.message(_("Name and Target cannot be empty."))
            else:
                if new_name != old_name:
                    del self.shortcuts[old_name]
                    
                self.shortcuts[new_name] = {
                    "type": sType,
                    "target": target,
                    "workdir": workdir if workdir else os.path.expanduser("~")
                }
                saveShortcuts(self.shortcuts)
                self.refreshList(new_name)
                ui.message(_("Shortcut updated"))
        dlg.Destroy()
        self.listCtrl.SetFocus()

    def onDelete(self, evt):
        selection = self.listCtrl.GetSelection()
        if selection != wx.NOT_FOUND:
            name = self.listCtrl.GetString(selection)
            del self.shortcuts[name]
            saveShortcuts(self.shortcuts)
            
            # Figure out which index to select next
            next_index = min(selection, self.listCtrl.GetCount() - 2) 
            self.refreshList()
            
            if self.listCtrl.GetCount() > 0:
                self.listCtrl.SetSelection(max(0, next_index))
            ui.message(_("Shortcut deleted"))
        else:
            ui.message(_("No shortcut selected"))
        self.listCtrl.SetFocus()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

    def __init__(self):
        super(GlobalPlugin, self).__init__()

    @script(
        description=_("Opens the ShortcutLaunch dialog to quickly launch a saved program, folder, or URL."),
        category="ShortcutLaunch",
        gesture="kb:NVDA+shift+l"
    )
    def script_openLauncher(self, gesture):
        wx.CallAfter(self._showLauncherDialog)

    def _showLauncherDialog(self):
        gui.mainFrame.prePopup()
        dlg = LauncherDialog(gui.mainFrame)
        gui.mainFrame.postPopup()
        
        if dlg.ShowModal() == wx.ID_OK:
            selection = dlg.listCtrl.GetSelection()
            if selection != wx.NOT_FOUND:
                name = dlg.listCtrl.GetString(selection)
                shortcut_data = dlg.shortcuts.get(name)
                if shortcut_data:
                    self.launchTarget(shortcut_data)
                
        dlg.Destroy()

    def launchTarget(self, data):
        target = data.get("target", "")
        sType = data.get("type", "Auto")
        workdir = data.get("workdir", os.path.expanduser("~"))
        
        try:
            if sType == "URL" or target.startswith("http"):
                webbrowser.open(target)
                ui.message(_("Launching URL"))
                
            elif sType in ["Program/File", "Folder", "Auto"] and os.path.exists(target):
                os.startfile(target)
                ui.message(f"Launching {sType}")
                
            else:
                if not os.path.isdir(workdir):
                    workdir = os.path.expanduser("~")
                subprocess.Popen(target, shell=True, cwd=workdir)
                ui.message(_("Launching command"))
                
        except Exception as e:
            ui.message(_("Failed to launch target"))
            log.error(f"ShortcutLaunch failed to launch {target}: {e}")