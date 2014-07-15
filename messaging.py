

class MessageHandler:
    """
    Convenience class for handling messaging.

    Includes a concept of progress, which is a measure of number of completed major and minor steps.

    For example, when processing a series of map services and their layers, the number of map services is the number of major
    steps, and the number of layers is the number of minor steps (represents loop-within-loop hierarchy).
    """

    def __init__(self,messages,logger=None):
        self.messages=messages
        self.logger=logger
        self.major_step=0
        self.major_steps=0
        self.minor_step=0
        self.minor_steps=0
        self._last_message=None

    def setMajorSteps(self,major_steps):
        """
        Set the number of major steps to measure progress against.

        :param major_steps: number of major steps of operation
        """

        self.major_steps=major_steps
        self.major_step=0
        self._updateMajorProgress()

    def setMinorSteps(self,minor_steps):
        """
        OPTIONAL: Set the number of minor steps to measure progress against.

        :param minor_steps: number of major steps of operation
        """

        self.minor_steps=minor_steps
        self.minor_step=0
        self._updateMajorProgress()

    def incrementMajorStep(self):
        """Increment the current major step by one, and emit a new progress message."""

        self.major_step+=1
        self._updateMajorProgress()

    def incrementMinorStep(self):
        """Increment the current minor step by one, and emit a new progress message."""

        self.minor_step+=1
        self._updateMinorProgress()

    def _getMajorProgress(self):
        return 100.0 * float(self.major_step) / float(self.major_steps) if self.major_steps else 0

    def _updateMajorProgress(self):
        self.setProgress(self._getMajorProgress())

    def _updateMinorProgress(self):
        minor_progress = 0
        if self.minor_steps:
            minor_progress = 100.0 * float(self.minor_step) / (float(self.major_steps) * float(self.minor_steps))
        self.setProgress(self._getMajorProgress() + minor_progress)

    def setProgress(self,progress):
        """
        Emit a new progress message: PROGRESS [PERCENT_COMPLETE]

        :param progress: the current progress, on a percent scale.
        """

        self.addMessage("PROGRESS: %.0f"%(progress))

    def addMessage(self,message):
        """
        Emit a new message to both messages and logger (if available)

        :param message: the message to emit
        """

        if message!=self._last_message:
            self._last_message=message
            self.messages.addMessage(message)
            if self.logger:
                self.logger.debug(message)

