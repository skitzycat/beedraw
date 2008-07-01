#!/usr/bin/env python

from collections import deque

class AbstractAction:
	def undo():
		pass
	def redo():
		pass

class ActionStack:
	def __init__(self):
		undostack=deque()
		redostack=deque()

	def undo(self):
		action=undostack.pop()
		action.undo()
		redostack.pushleft(action)

	def redo(self):
		if len(redostack) > 0:
			action=redostack.pop()
			action.redo()
			undostack.pushleft(action)

	def addAction(self,action):
		redostack.clear()
		undostack.pushleft(action)
