main: BeeMasterUI.py DrawingWindowUI.py LayerWidgetUi.py LayersWindowUi.py HiveMasterUi.py HiveOptionsUi.py ImageSizeAdjustDialogUi.py ConnectionDialogUi.py ImageScaleDialog.py PencilOptionsDialogUi.py BrushOptionsDialogUi.py EraserOptionsDialogUi.py PaintBucketOptionsDialogUi.py

%.py : %.ui
	pyuic4 $< > $@

clean:
	rm -f *.py *.pyc

.PHONY: clean main
