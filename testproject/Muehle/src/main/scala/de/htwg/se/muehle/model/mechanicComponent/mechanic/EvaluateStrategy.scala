package de.htwg.se.muehle.model.mechanicComponent.mechanic

import de.htwg.se.muehle.model.gameFieldComponent.gameFieldInterface
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.Stone

trait EvaluateStrategy {
  def checkForMuehle(field: gameFieldInterface, newRing: Int, newPosOnRing: Int, stone: Stone): Boolean
}
