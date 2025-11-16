
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import sys
import os

class OpenAlgoUpgradeService(win32serviceutil.ServiceFramework):
    _svc_name_ = "OpenAlgoUpgradeService"
    _svc_display_name_ = "OpenAlgo Automatic Upgrade Service"
    _svc_description_ = "Automatically monitors and upgrades OpenAlgo for Fortress Trading System"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False
        
    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                            servicemanager.PYS_SERVICE_STARTED,
                            (self._svc_name_, ''))
        
        while self.running:
            try:
                # Run upgrade check
                script_path = r"C:\Users\Admin\Documents\FortressTradingSystem\openalgo_upgrade_system.py"
                python_path = r"C:\Users\Admin\Documents\FortressTradingSystem\.venv314\Scripts\python.exe"
                subprocess.run([python_path, script_path, "--check"], timeout=300)
                
                # Wait for next check (24 hours)
                win32event.WaitForSingleObject(self.hWaitStop, 24 * 60 * 60 * 1000)
                
            except Exception as e:
                servicemanager.LogErrorMsg(f"Service error: {str(e)}")
                # Wait 1 hour before retry on error
                win32event.WaitForSingleObject(self.hWaitStop, 60 * 60 * 1000)

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(OpenAlgoUpgradeService)
