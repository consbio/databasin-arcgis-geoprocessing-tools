"""
Convenience class for handling messaging between versions of ArcGIS
"""

import arcpy

class MessageHandler:
    def __init__(self,messages=None,logger=None):
        """
        messages are only supported in ArcGIS 10.1
        """
        self.messages=messages
        self.logger=logger
        self.major_step=0
        self.major_steps=0
        self.minor_step=0
        self.minor_steps=0
        self._last_message=None

    def setMajorSteps(self,major_steps):
        self.major_steps=major_steps
        self.major_step=0
        self._updateMajorProgress()

    def setMinorSteps(self,minor_steps):
        self.minor_steps=minor_steps
        self.minor_step=0
        self._updateMinorProgress()

    def incrementMajorStep(self):
        self.major_step+=1
        self._updateMajorProgress()

    def incrementMinorStep(self):
        self.minor_step+=1
        self._updateMinorProgress()

    def _updateMajorProgress(self):
        progress=0
        if self.major_steps>0:
            progress = 100.0 * float(self.major_step) / float(self.major_steps)
        self.setProgress(progress)

    def _updateMinorProgress(self):
        progress=0
        if self.major_steps>0 and self.minor_steps>0:
            progress = (100.0 * float(self.minor_step) / float(self.minor_steps))  / self.major_steps
        self.setProgress(progress)


    def setProgress(self,progress):
        self.addMessage("PROGRESS: %.0f"%(progress))

    def addMessage(self,message):
        if message!=self._last_message:
            self._last_message=message
            if self.messages:
                self.messages.addMessage(message)
            else:
                arcpy.AddMessage(message)
            if self.logger:
                self.logger.debug(message)

