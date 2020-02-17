import os
import vtk, qt, ctk, slicer
import logging
import subprocess
from SegmentEditorEffects import *

class SegmentEditorEffect(AbstractScriptedSegmentEditorEffect):
  """This effect uses Watershed algorithm to partition the input volume"""

  def __init__(self, scriptedEffect):
    scriptedEffect.name = 'PreformSE'
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
    iconPath = "D:\\Formlabs.jpg"
    #iconPath = os.path.join(os.path.dirname(__file__), 'SegmentEditorEffect.png')
    if os.path.exists(iconPath):
      return qt.QIcon(iconPath)
    return qt.QIcon()

  def helpText(self):
    return """Selected segment is exported as 3D model to PreForm.
This effect automatically generates a 3D surface model and opens it in Formlabs PreForm, official Formlabs software
for 3D printing setup and management.
"""

  def setupOptionsFrame(self):
    # PreForm path
    self.preformPath = ctk.ctkPathLineEdit()
    self.scriptedEffect.addLabeledOptionsWidget("Preform Path:", self.preformPath)

    # PreForm start flags
    self.enableAutoRepairCheckBox = qt.QCheckBox()
    self.enableAutoRepairCheckBox.checked = 1
    self.scriptedEffect.addLabeledOptionsWidget("Auto Repair:", self.enableAutoRepairCheckBox)

    # Apply button
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.objectName = self.__class__.__name__ + 'Apply'
    self.applyButton.setToolTip("Accept previewed result")
    self.scriptedEffect.addOptionsWidget(self.applyButton)
    self.applyButton.connect('clicked()', self.onApply)

  def createCursor(self, widget):
    # Turn off effect-specific cursor for this effect
    return slicer.util.mainWindow().cursor

  def onApply(self):
    logging.info('Processing started')

    # Get list of visible segment IDs, as the effect ignores hidden segments.
    segmentationNode = self.scriptedEffect.parameterSetNode().GetSegmentationNode()
    visibleSegmentIds = vtk.vtkStringArray()
    segmentationNode.GetDisplayNode().GetVisibleSegmentIDs(visibleSegmentIds)
    if visibleSegmentIds.GetNumberOfValues() == 0:
      logging.info("Smoothing operation skipped: there are no visible segments")
      return

    exportPath = "D:\\"

    # Export to STL
    slicer.vtkSlicerSegmentationsModuleLogic.ExportSegmentsClosedSurfaceRepresentationToFiles(
      exportPath,
      segmentationNode,
      None
    )

    # D:\Programs\Formlabs\PreForm\PreForm.exe
    # Get paths to STL models
    stlFilename = "Segmentation_Angio_Segment_1.stl"
    stlFilepath = exportPath + stlFilename

    # Process params
    params = ""
    params += " --silentRepair"
    params += " --diagnostic"

    # Open Preform
    logging.info("Opening PreForm")
    #p = subprocess.check_output(preformPath + " " + stlFilepath + params)
    preformPath = "D:\\Programs\\Formlabs\\PreForm\\PreForm.exe"
    p = subprocess.Popen(preformPath + " " + stlFilepath + params)
    logging.info(p)

    logging.info('Processing completed')


    """# Get list of visible segment IDs, as the effect ignores hidden segments.
    segmentationNode = self.scriptedEffect.parameterSetNode().GetSegmentationNode()
    visibleSegmentIds = vtk.vtkStringArray()
    segmentationNode.GetDisplayNode().GetVisibleSegmentIDs(visibleSegmentIds)
    if visibleSegmentIds.GetNumberOfValues() == 0:
      logging.info("Smoothing operation skipped: there are no visible segments")
      return

    # This can be a long operation - indicate it to the user
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

    # Allow users revert to this state by clicking Undo
    self.scriptedEffect.saveStateForUndo()

    # Export master image data to temporary new volume node.
    # Note: Although the original master volume node is already in the scene, we do not use it here,
    # because the master volume may have been resampled to match segmentation geometry.
    import vtkSegmentationCorePython as vtkSegmentationCore
    masterVolumeNode = slicer.vtkMRMLScalarVolumeNode()
    slicer.mrmlScene.AddNode(masterVolumeNode)
    masterVolumeNode.SetAndObserveTransformNodeID(segmentationNode.GetTransformNodeID())
    slicer.vtkSlicerSegmentationsModuleLogic.CopyOrientedImageDataToVolumeNode(self.scriptedEffect.masterVolumeImageData(), masterVolumeNode)
    # Generate merged labelmap of all visible segments, as the filter expects a single labelmap with all the labels.
    mergedLabelmapNode = slicer.vtkMRMLLabelMapVolumeNode()
    slicer.mrmlScene.AddNode(mergedLabelmapNode)
    slicer.vtkSlicerSegmentationsModuleLogic.ExportSegmentsToLabelmapNode(segmentationNode, visibleSegmentIds, mergedLabelmapNode, masterVolumeNode)

    # Run segmentation algorithm
    import SimpleITK as sitk
    import sitkUtils
    # Read input data from Slicer into SimpleITK
    labelImage = sitk.ReadImage(sitkUtils.GetSlicerITKReadWriteAddress(mergedLabelmapNode.GetName()))
    backgroundImage = sitk.ReadImage(sitkUtils.GetSlicerITKReadWriteAddress(masterVolumeNode.GetName()))
    # Run watershed filter
    featureImage = sitk.GradientMagnitudeRecursiveGaussian(backgroundImage, float(self.scriptedEffect.doubleParameter("ObjectScaleMm")))
    del backgroundImage
    f = sitk.MorphologicalWatershedFromMarkersImageFilter()
    f.SetMarkWatershedLine(False)
    f.SetFullyConnected(False)
    labelImage = f.Execute(featureImage, labelImage)
    del featureImage
    # Pixel type of watershed output is the same as the input. Convert it to int16 now.
    if labelImage.GetPixelID() != sitk.sitkInt16:
      labelImage = sitk.Cast(labelImage, sitk.sitkInt16)
    # Write result from SimpleITK to Slicer. This currently performs a deep copy of the bulk data.
    sitk.WriteImage(labelImage, sitkUtils.GetSlicerITKReadWriteAddress(mergedLabelmapNode.GetName()))
    mergedLabelmapNode.GetImageData().Modified()
    mergedLabelmapNode.Modified()

    # Update segmentation from labelmap node and remove temporary nodes
    slicer.vtkSlicerSegmentationsModuleLogic.ImportLabelmapToSegmentationNode(mergedLabelmapNode, segmentationNode, visibleSegmentIds)
    slicer.mrmlScene.RemoveNode(masterVolumeNode)
    slicer.mrmlScene.RemoveNode(mergedLabelmapNode)

    qt.QApplication.restoreOverrideCursor()"""
