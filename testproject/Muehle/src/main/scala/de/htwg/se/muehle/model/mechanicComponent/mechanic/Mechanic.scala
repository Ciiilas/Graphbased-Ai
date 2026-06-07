package de.htwg.se.muehle.model.mechanicComponent.mechanic

import com.google.inject.Inject

import de.htwg.se.muehle.model.gameComponent.PlayerState
import de.htwg.se.muehle.model.gameFieldComponent.gameFieldInterface
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.{Gamefield, Stone}
import de.htwg.se.muehle.model.mechanicComponent.mechanicInterface
import play.api.libs.json._

case class Mechanic @Inject (
                              CounterOfSetStone: Int = 0, 
                              evaluateStrategy: EvaluateStrategy = new ComplexEvaluateStrategy
                            ) extends mechanicInterface {

  override def getEvaluateStrategy: EvaluateStrategy = evaluateStrategy

  override def getCounterOfSetStone: Int = CounterOfSetStone

  def countStones(field: gameFieldInterface, stoneColor: Stone): Int = {
    field.getMuehleMatrix.flatten.count((stone: Stone) => stone == stoneColor)
  }

  def isSetLegal(field: gameFieldInterface, ring: Int, posOnRing: Int): Boolean = {
    if (!(ring >= 0 && ring < field.getMuehleMatrix.size &&
        posOnRing >= 0 && posOnRing < field.getMuehleMatrix(ring).size)) {
      return false
    }
    if (field.getMuehleMatrix(ring)(posOnRing) == Stone.Empty) {
      true
    } else {
      false
    }
  }

  def setStone(field: gameFieldInterface, ring: Int, posOnRing: Int, stone: Stone): (Mechanic, gameFieldInterface) = {
    if (isSetLegal(field, ring, posOnRing)) {
      val updateRing: Vector[Vector[Stone]] = field.getMuehleMatrix.updated(ring, field.getMuehleMatrix(ring).updated(posOnRing, stone))
      val newMechanic = this.copy(CounterOfSetStone = this.CounterOfSetStone + 1)
      (newMechanic, Gamefield(updateRing))
    } else {
      (this, field)
    }
  }


  def isMoveAllowed(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int): Boolean = {
    // Prüfen, ob die neue Position innerhalb der Spielfeldgrenzen liegt
    val isWithinBounds =
      newRing >= 0 && newRing < field.getMuehleMatrix.size &&
      newPosOnRing >= 0 && newPosOnRing < field.getMuehleMatrix(newRing).size

    // Prüfen, ob die Bewegung eine Position entlang des Rings ist
    val isSameRingMove =
      oldRing == newRing &&
        (newPosOnRing == (oldPosOnRing + 1) % 8 || newPosOnRing == (oldPosOnRing - 1 + 8) % 8) // zyklische Bewegung

    // Prüfen, ob der Ringwechsel erlaubt ist
    val isValidRingMove = (oldRing, newRing) match {
      case (0, 1) | (1, 0) | (1, 2) | (2, 1) => true
      case _ => false
    }

    // Prüfen, ob die Bewegung erlaubt ist
    val isEvenPosition = oldPosOnRing % 2 == 0

    isWithinBounds && (
      isSameRingMove || // Bewegung auf demselben Ring
        (!isEvenPosition && isValidRingMove) // Ringwechsel nur, wenn ungerade Position
      )
  }


  def isMoveLegal(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int, stone: Stone): Boolean = {
    //when Stone on oldPos equals the player Stone then continue

    if (!(field.getMuehleMatrix(oldRing)(oldPosOnRing) == stone)) {
        return false
      }
      //when Stone on newPos equals the player Stone then continue
      if (!(field.getMuehleMatrix(newRing)(newPosOnRing) == Stone.Empty)) {
        return false
      }

      if (isMoveAllowed(field, oldRing, oldPosOnRing, newRing, newPosOnRing)) {
        true
      } else {
        false
      }
  }

  def moveStone(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int, stone: Stone): gameFieldInterface = {
    if (isMoveLegal(field, oldRing, oldPosOnRing, newRing, newPosOnRing, stone)) {
      val removeStone: Vector[Vector[Stone]] = field.getMuehleMatrix.updated(oldRing, field.getMuehleMatrix(oldRing).updated(oldPosOnRing, Stone.Empty))
      val placeStone: Vector[Vector[Stone]] = removeStone.updated(newRing, removeStone(newRing).updated(newPosOnRing, stone))
      Gamefield(placeStone)
    } else {
      field
    }
  }

  def isJumpLegal(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int, stone: Stone): Boolean = {
    if (!(oldRing >= 0 && oldRing < field.getMuehleMatrix.size &&
      oldPosOnRing >= 0 && oldPosOnRing < field.getMuehleMatrix(oldRing).size)) {
      return false
    }
    if (!(newRing >= 0 && newRing < field.getMuehleMatrix.size &&
      newPosOnRing >= 0 && newPosOnRing < field.getMuehleMatrix(newRing).size)) {
      return false
    }

    if (!(field.getMuehleMatrix(oldRing)(oldPosOnRing) == stone)) {
      return false
    }
    //when Stone on newPos equals the player Stone then continue
    if (!(field.getMuehleMatrix(newRing)(newPosOnRing) == Stone.Empty)) {
      return false
    }
    true
  }

  def jumpStone(field: gameFieldInterface, oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int, stone: Stone): gameFieldInterface = {
    if (isJumpLegal(field, oldRing, oldPosOnRing, newRing, newPosOnRing, stone)) {
      val removeStone = field.getMuehleMatrix.updated(oldRing, field.getMuehleMatrix(oldRing).updated(oldPosOnRing, Stone.Empty))
      val placeStone = removeStone.updated(newRing, removeStone(newRing).updated(newPosOnRing, stone))
      Gamefield(placeStone)
    } else {
      field
    }
  }

  def isRemoveLegal(field: gameFieldInterface, ring: Int, posOnRing: Int, stone: Stone): Boolean = {
    PlayerState.next()
    val opponentStone = PlayerState.stone
    PlayerState.next()

    if (!(ring >= 0 && ring < field.getMuehleMatrix.size &&
      posOnRing >= 0 && posOnRing < field.getMuehleMatrix(ring).size)) {
      return false
    }

    if (field.getMuehleMatrix(ring)(posOnRing) == stone) {
      return false
    }

    if (field.getMuehleMatrix(ring)(posOnRing) == Stone.Empty) {
      return false
    }

    if (evaluateStrategy.checkForMuehle(field, ring, posOnRing, opponentStone)) {
      val removableStones = for {
        r <- field.getMuehleMatrix.indices
        p <- field.getMuehleMatrix(r).indices
        if field.getMuehleMatrix(r)(p) == opponentStone && !evaluateStrategy.checkForMuehle(field, r, p, opponentStone)
      } yield (r, p)

      if (removableStones.nonEmpty) {
        return false
      }
    }
    true
  }

  def removeStone(field: gameFieldInterface, ring: Int, posOnRing: Int, stone: Stone): gameFieldInterface = {
    if (isRemoveLegal(field, ring, posOnRing, stone)) {
      val updateRing = field.getMuehleMatrix.updated(ring, field.getMuehleMatrix(ring).updated(posOnRing, Stone.Empty))
      Gamefield(updateRing)
    } else {
      field
    }
  }
}

object Mechanic {
  implicit val writes: Writes[Mechanic] = Writes {
    mechanic =>
      Json.obj(
        "counterOfSetStone" -> mechanic.CounterOfSetStone
      )
  }
  
  implicit val reads: Reads[Mechanic] = Reads {
    json =>
      for {
        counterOfSetStone <- (json \ "counterOfSetStone").validate[Int]
      } yield Mechanic(counterOfSetStone)
  }
}