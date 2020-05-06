import os
import vtk, qt, ctk, slicer
import logging
import subprocess
import platform
import winreg
from SegmentEditorEffects import *

class SegmentEditorEffect(AbstractScriptedSegmentEditorEffect):
  """This module-effect allows to export the segmentation directly
  to the PreForm (Formlabs) 3D printing software"""

  def __init__(self, scriptedEffect):
    scriptedEffect.name = 'Preform'
    scriptedEffect.perSegment = False # this effect operates on all segments at once (not on a single selected segment)
    scriptedEffect.requireSegments = True # this effect requires segment(s) existing in the segmentation
    AbstractScriptedSegmentEditorEffect.__init__(self, scriptedEffect)

  def clone(self):
    # It should not be necessary to modify this method
    import qSlicerSegmentationsEditorEffectsPythonQt as effects
    clonedEffect = effects.qSlicerSegmentEditorScriptedEffect(None)
    clonedEffect.setPythonSource(__file__.replace('\\','/'))
    return clonedEffect

  def icon(self):
    # It should not be necessary to modify this method
    iconPath = os.path.join(os.path.dirname(__file__), 'PreformIcon.jpg')
    if os.path.exists(iconPath):
      return qt.QIcon(iconPath)
    return qt.QIcon()

  def helpText(self):
    return """Selected segment is exported as 3D model to PreForm.

    This effect automatically generates a 3D surface model and opens it in
    Formlabs PreForm, official Formlabs software for 3D printing setup and management.

    Only selected (active) segment from the current (active) Segmentation
    will be exported.
    """

  def setupOptionsFrame(self):
    # PreForm path
    self.preformPath = ctk.ctkPathLineEdit()
    if platform.system() == 'Windows':
      try:
        key_to_read = r'SOFTWARE\WOW6432Node\PreForm'
        reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        k = winreg.OpenKey(reg, key_to_read)
        value, regtype = winreg.QueryValueEx(k, 'Path')
        self.preformPath.currentPath = value + '\PreForm.exe'
      except WindowsError as e:
        logging.info(e)
    elif platform.system() == 'Darwin':
      self.preformPath.currentPath = '/Applications/PreForm.app/Contents/MacOS/PreForm'

    self.scriptedEffect.addLabeledOptionsWidget("Path to PreForm.exe:", self.preformPath)

    # Select segments
    self.mergeAllVisibleSegments = qt.QCheckBox()
    self.mergeAllVisibleSegments.checked = 0
    self.mergeAllVisibleSegments.setToolTip("""If checked, you will merge all
     visible segments into one object and export. If not, only selected
     segment will be exported""")
    self.scriptedEffect.addLabeledOptionsWidget("Merge&export all visible segments:", self.mergeAllVisibleSegments)

    # PreForm start flags
    self.enableAutoRepairCheckBox = qt.QCheckBox()
    self.enableAutoRepairCheckBox.checked = 1
    self.enableAutoRepairCheckBox.setToolTip("""If checked, exported model
    will be automatically checked for structural errors and repaired
    by PreForm at load""")
    self.scriptedEffect.addLabeledOptionsWidget("Auto Repair:", self.enableAutoRepairCheckBox)

    # Path to save STL file
    # It's necessary to have a saved STL file for this
    self.stlExportPath = ctk.ctkPathLineEdit()
    self.stlExportPath.setCurrentPath(os.getcwd())
    self.scriptedEffect.addLabeledOptionsWidget("Path to store STL files:", self.stlExportPath)

    # Export button
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.objectName = self.__class__.__name__ + 'Apply'
    self.applyButton.setToolTip("Export segment(s) to PreForm")
    self.scriptedEffect.addOptionsWidget(self.applyButton)
    self.applyButton.connect('clicked()', self.onApply)

  def createCursor(self, widget):
    # Turn off effect-specific cursor for this effect
    return slicer.util.mainWindow().cursor

  def getSegmentToExport(self):
    # This method returns a segment to export
    # Return is a vtk Segment object
    # To export, this has to be converted to vtkStringArray

    # Currently selected (active) segment
    segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor
    segmentEditorNode = segmentEditorWidget.mrmlSegmentEditorNode()
    selectedSegmentID = segmentEditorNode.GetSelectedSegmentID()

    # Get segment as a VTK object
    segmentationNode = self.scriptedEffect.parameterSetNode().GetSegmentationNode()
    segmentationNodeName = segmentationNode.GetName()
    segmentation = segmentationNode.GetSegmentation()
    segment = segmentation.GetSegment(selectedSegmentID)

    return selectedSegmentID, segment.GetName()

  def onApply(self):
    # If exporting single selected element, get the segment ID and name
    if not self.mergeAllVisibleSegments.checked:
      segmentToExportID, segmentToExportName = self.getSegmentToExport()
      segmentVtkStringArray = vtk.vtkStringArray()
      segmentVtkStringArray.InsertNextValue(segmentToExportID)

    # STL will be exported to a current working directory
    exportPath = self.stlExportPath.currentPath

    # Model from merged objects will be saved under segmentation node name
    # From single segments, they will get a "SegmentationNodeName_SegmentName.stl" format
    segmentationNode = self.scriptedEffect.parameterSetNode().GetSegmentationNode()
    segmentationNodeName = segmentationNode.GetName()

    # Export segmentation nodes/segments to STL
    if self.mergeAllVisibleSegments.checked:
      # All segments
      slicer.vtkSlicerSegmentationsModuleLogic.ExportSegmentsClosedSurfaceRepresentationToFiles(
        exportPath,
        segmentationNode,
        None,
        "STL",
        True,
        1.0,
        True
      )
      stlFilepath = os.path.join(exportPath, (segmentationNodeName + '.stl'))
    else:
      # Only selected segment
      slicer.vtkSlicerSegmentationsModuleLogic.ExportSegmentsClosedSurfaceRepresentationToFiles(
        exportPath,
        segmentationNode,
        segmentVtkStringArray,
        "STL",
        True,
        1.0,
        False
      )
      stlFilepath = os.path.join(exportPath, (segmentationNodeName + "_" + segmentToExportName + ".stl"))

    # Open Preform
    preformPath = self.preformPath.currentPath
    logging.info("Saving STL in:")
    logging.info(stlFilepath)

    # Create a copy of the environment
    # Without this, qt conflict blocks Preform from starting
    newQtPluginPath = "".join(preformPath.split(".")[:-1])
    my_env = os.environ.copy()
    my_env["QT_PLUGIN_PATH"] = newQtPluginPath

    if self.enableAutoRepairCheckBox.checked:
      p = subprocess.Popen([preformPath, stlFilepath, '--silentRepair', '--diagnostic'], env=my_env, shell=True)
    else:
      p = subprocess.Popen([preformPath, stlFilepath, '--diagnostic'], env=my_env, shell=True)

    logging.info(p)