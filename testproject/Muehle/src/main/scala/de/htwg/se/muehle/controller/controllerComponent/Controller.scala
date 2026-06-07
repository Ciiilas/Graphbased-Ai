package de.htwg.se.muehle.controller.controllerComponent

import de.htwg.se.muehle.controller.*
import de.htwg.se.muehle.model.gameComponent.{Game, PlayerState}
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.{Stone, meshComponentInterface}
import de.htwg.se.muehle.model.{GameStateEnum, gameInterface}
import de.htwg.se.muehle.model.FileIOComponent.FileIOComponent
import de.htwg.se.muehle.util.{Command, Event, Observable, UndoManager}
import de.htwg.se.muehle.MuehleModule
import com.google.inject.{Guice, Inject, Injector}


case class Controller @Inject() (var game: gameInterface, fileIOComponent: FileIOComponent) extends controllerInterface with Observable {
  
  
  private val injector: Injector = Guice.createInjector(new MuehleModule)

  override def getGame: gameInterface = game
  
  //-----------------------------------------------------
  //undoManager
  //-----------------------------------------------------
  
  
  private val undoManager = new UndoManager[gameInterface]


  def undo(): Unit = {
    game = undoManager.undoStep(game)
    PlayerState.stone = game.getPlayer
    notifyObservers(Event.Set)
  }

  //-----------------------------------------------------
  //mechanic with undoManager inclusive
  //-----------------------------------------------------
  

  def getGameState: GameStateEnum = {
    game.getCurrentGameState
  }

  def doStep(command: Command[gameInterface]): Unit = {
    game = undoManager.doStep(game, command)
    notifyObservers(Event.Set)
  }

  def setStone(newRing: Int, newPosOnRing: Int): Unit = {
    doStep(new SetCommand(game, newRing, newPosOnRing))
  }

  def moveStone(oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int): Unit = {
    doStep(new MoveCommand(game, oldRing, oldPosOnRing, newRing, newPosOnRing))
  }

  def jumpStone(oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int): Unit = {
    doStep(new JumpCommand(game, oldRing, oldPosOnRing, newRing, newPosOnRing))
  }

  def removeStone(newRing: Int, newPosOnRing: Int): Unit = {
    doStep(new RemoveCommand(game, newRing, newPosOnRing))
  }
  
  def sendGameOver(message: Option[String]): Unit = {
    notifyObservers(Event.GameOver)
  }

  //-----------------------------------------------------
  //field
  //-----------------------------------------------------
  
  override def toString: String = game.getGameField.getMuehleMatrix.toString

  def getMuehleMatrix: Vector[Vector[Stone]] = {
    game.getGameField.getMuehleMatrix
  }

  def setDecorator(enabled: Boolean): Unit = {
    game.setDecorator(enabled)
  }

  def getMesh(): meshComponentInterface = {
    game.getMesh
  }
  
  def getCurrentPlayer: Stone = {
    game.getPlayer
  }
  
  def getOpponentPlayer: Stone = {
    game.getOpponentPlayer
  }
  
  //-----------------------------------------------------
  //load/save
  //-----------------------------------------------------
  
  def load(): Unit = {
    this.game = fileIOComponent.load()
    notifyObservers(Event.Load)
  }
  
  def save(): Unit = {
    fileIOComponent.save(game)
    notifyObservers(Event.Save)
  }
}

