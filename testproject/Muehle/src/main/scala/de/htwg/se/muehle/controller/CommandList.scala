package de.htwg.se.muehle.controller

import de.htwg.se.muehle.model.gameInterface
import de.htwg.se.muehle.util.Command

class SetCommand(game: gameInterface, newRing: Int, newPosOnRing: Int) extends Command[gameInterface] {
  private var memento: gameInterface = game
  override def doStep(game: gameInterface): gameInterface = {
    memento = game
    game.setStoneGame(newRing, newPosOnRing)
  }

  override def undoStep(game: gameInterface): gameInterface = {
    memento
  }
}

class MoveCommand(game: gameInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int) extends Command[gameInterface] {
  private var memento: gameInterface = game
  
  override def doStep(game: gameInterface): gameInterface = {
    memento = game
    game.moveStoneGame(oldRing, oldPosOnRing, newRing, newPosOnRing)
  }

  override def undoStep(game: gameInterface): gameInterface = {
    memento
  }
}

class JumpCommand(game: gameInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int) extends Command[gameInterface] {
  private var memento: gameInterface = game

  override def doStep(game: gameInterface): gameInterface = {
    memento = game
    game.jumpStoneGame(oldRing, oldPosOnRing, newRing, newPosOnRing)
  }

  override def undoStep(game: gameInterface): gameInterface = {
    memento
  }
}

class RemoveCommand(game: gameInterface, newRing: Int, newPosOnRing: Int) extends Command[gameInterface] {
  private var memento: gameInterface = game

  override def doStep(game: gameInterface): gameInterface = {
    memento = game
    game.removeStoneGame(newRing, newPosOnRing)
  }

  override def undoStep(game: gameInterface): gameInterface = {
    memento
  }
}
