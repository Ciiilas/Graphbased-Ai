package de.htwg.se.muehle.model.mechanicComponent

import de.htwg.se.muehle.model.gameFieldComponent.gameFieldInterface
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.{Gamefield, Stone}
import de.htwg.se.muehle.model.mechanicComponent.mechanic.{EvaluateStrategy, Mechanic}
import play.api.libs.json._

trait mechanicInterface {
  //Getter
  def getEvaluateStrategy: EvaluateStrategy
  def getCounterOfSetStone: Int
  
  //Methoden
  def countStones(field: gameFieldInterface, stoneColor: Stone): Int
  def isSetLegal(field: gameFieldInterface, ring: Int, posOnRing: Int): Boolean
  def setStone(field: gameFieldInterface, ring: Int, posOnRing: Int, stone: Stone): (mechanicInterface, gameFieldInterface)
  def isMoveAllowed(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int): Boolean
  def isMoveLegal(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int, stone: Stone): Boolean
  def moveStone(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int, stone: Stone): gameFieldInterface
  def isJumpLegal(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int, stone: Stone): Boolean
  def jumpStone(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int, stone: Stone): gameFieldInterface
  def isRemoveLegal(field: gameFieldInterface, ring: Int, posOnRing: Int, stone: Stone): Boolean
  def removeStone(field: gameFieldInterface, ring: Int, posOnRing: Int, stone: Stone): gameFieldInterface
}



object mechanicInterface {
  implicit val writes: Writes[mechanicInterface] = Writes {
    case mechanic: Mechanic => Json.toJson(mechanic)(Mechanic.writes)
    case _ => throw new IllegalArgumentException("Unknown mechanicInterface implementation")
  }

  implicit val reads: Reads[mechanicInterface] = Reads {
    json => json.validate[Mechanic](Mechanic.reads)
  }
}