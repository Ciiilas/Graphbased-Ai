package de.htwg.se.muehle.model.mechanicComponent.mechanic

import de.htwg.se.muehle.model.gameFieldComponent.gameFieldInterface
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.Stone

class ComplexEvaluateStrategy extends EvaluateStrategy {
  override def checkForMuehle(field: gameFieldInterface, newRing: Int, newPosOnRing: Int, stone: Stone): Boolean = {
      //check Muehle from Ring Center
      if (newPosOnRing % 2 == 1) {
        //checking On Ring
        if (field.getMuehleMatrix(newRing)((newPosOnRing - 1 + 8) % 8) == stone && field.getMuehleMatrix(newRing)((newPosOnRing + 1) % 8) == stone) {
          return true
        }
        //checking other Rings
        if (field.getMuehleMatrix((newRing - 1 + 3) % 3)(newPosOnRing) == stone && field.getMuehleMatrix((newRing + 1) % 3)(newPosOnRing) == stone) {
          return true
        }
        return false
      }
      //check Muehle from Ring Corner
      if (newPosOnRing % 2 == 0) {
        //Corner right
        if (field.getMuehleMatrix(newRing)((newPosOnRing - 1 + 8) % 8) == stone && field.getMuehleMatrix(newRing)((newPosOnRing - 2 + 8) % 8) == stone
          || field.getMuehleMatrix(newRing)((newPosOnRing + 1) % 8) == stone && field.getMuehleMatrix(newRing)((newPosOnRing + 2) % 8) == stone) {
          return true
        }
      }
      false
    }
}
